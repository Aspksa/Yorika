"""Offline research architecture, deliberately not a chat/checkpoint replacement.

Shared recurrent block, learned top-2 experts, differentiable optional memory slots,
and identity-initialized depth growth. More compute does not guarantee better answers.
The ordinary dense checkpoint loader intentionally does not accept this architecture.
"""
import copy
import math


def make_adaptive(torch, *, vocab=261, width=32, heads=2, experts=4, context=64):
    from torch import nn
    if (any(type(v) is not int for v in (vocab, width, heads, experts, context)) or
            not 261 <= vocab <= 4357 or not 16 <= width <= 640 or
            not 1 <= heads <= 16 or width % heads or not 2 <= experts <= 8 or not 32 <= context <= 512):
        raise ValueError("Invalid bounded adaptive architecture")

    class ExpertBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(width)
            self.attention = nn.MultiheadAttention(width, heads, dropout=0., batch_first=True)
            self.router = nn.Linear(width, experts)
            self.experts = nn.ModuleList([nn.Sequential(nn.Linear(width, 2 * width), nn.GELU(),
                                                       nn.Linear(2 * width, width)) for _ in range(experts)])
            self.memory_query = nn.Linear(width, width, bias=False)
            self.memory_value = nn.Linear(width, width, bias=False)

        def forward(self, x, memory=None):
            n = self.norm(x)
            mask = torch.ones(x.shape[1], x.shape[1], dtype=torch.bool, device=x.device).triu(1)
            attended, _ = self.attention(n, n, n, attn_mask=mask, need_weights=False)
            x = x + attended
            flat = self.norm(x).reshape(-1, width)
            probabilities = self.router(flat).softmax(-1)
            weights, indices = probabilities.topk(2, dim=-1)
            weights = weights / weights.sum(-1, keepdim=True)
            mixed = torch.zeros_like(flat)
            # Dispatch only selected tokens to each expert; all expert weights remain resident.
            for index, expert in enumerate(self.experts):
                token, slot = (indices == index).nonzero(as_tuple=True)
                if token.numel():
                    contribution = expert(flat[token]) * weights[token, slot, None]
                    mixed = mixed.index_add(0, token, contribution)
            x = x + mixed.reshape_as(x)
            if memory is not None:
                if (memory.ndim != 3 or memory.shape[0] != x.shape[0] or
                        memory.shape[2] != width or not 1 <= memory.shape[1] <= 128):
                    raise ValueError("Memory must be batch x slots(1..128) x width")
                affinity = (self.memory_query(x) @ memory.transpose(-1, -2)) / math.sqrt(width)
                x = x + affinity.softmax(-1) @ self.memory_value(memory)
            # Balancing term is exposed to the experiment trainer, never mistaken for quality.
            frequency = torch.nn.functional.one_hot(indices, experts).float().mean((0, 1)).detach()
            return x, experts * (probabilities.mean(0) * frequency).sum()

    class GrowthBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(width)
            self.up = nn.Linear(width, width * 2)
            self.down = nn.Linear(width * 2, width)
            nn.init.zeros_(self.down.weight)
            nn.init.zeros_(self.down.bias)

        def forward(self, x):
            return x + self.down(torch.nn.functional.gelu(self.up(self.norm(x))))

    class AdaptiveBrain(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(vocab, width)
            self.position = nn.Embedding(context, width)
            self.shared = ExpertBlock()
            self.growth = nn.ModuleList()
            self.output = nn.Linear(width, vocab)

        def forward(self, ids, *, passes=1, memory=None):
            if type(passes) is not int or not 1 <= passes <= 8:
                raise ValueError("Recurrence budget must be 1..8")
            if ids.ndim != 2 or not 1 <= ids.shape[1] <= context:
                raise ValueError("Invalid context")
            x = self.embedding(ids) + self.position(torch.arange(ids.shape[1], device=ids.device))
            auxiliary = 0.
            for _ in range(passes):
                x, balance = self.shared(x, memory)
                auxiliary = auxiliary + balance
            for block in self.growth:
                x = block(x)
            return self.output(x), auxiliary / passes

        def grown_copy(self):
            if len(self.growth) >= 8:
                raise ValueError("Growth budget exhausted")
            result = copy.deepcopy(self)
            result.growth.append(GrowthBlock().to(device=self.output.weight.device,
                                                  dtype=self.output.weight.dtype))
            # Caller constructs a fresh optimizer; this is not exact optimizer resume.
            return result

    return AdaptiveBrain()


def weight_budget(parameters):
    """Weight storage lower bounds only; NOT a claim about actual VRAM consumption."""
    if type(parameters) is not int or parameters < 1:
        raise ValueError("Positive parameter count required")
    return {"fp32_weight_bytes": parameters * 4, "fp16_weight_bytes": parameters * 2,
            "int4_weight_bytes_lower_bound": (parameters + 1) // 2,
            "fp32_adam_training_bytes_lower_bound": parameters * 16,
            "excludes": "activations, attention/KV, quantization scales, temporary buffers, runtime"}
