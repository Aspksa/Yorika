"""Newer brain parts for the "lab" network. Each starts as an exact identity (its output
projection is zero), so a version can grow with them and evolution can switch them on.

- Scan (mixer "ssm"): a selective state-space layer in the spirit of Mamba. Every channel keeps
  a small state that forgets at a speed chosen from the current token; no attention matrix.
- Scan (mixer "liquid"): liquid time constants. Each channel moves toward a target at its own
  speed, and that speed depends on the input. This is the parallel, simplified form: the speed
  depends on the token, not on the state itself, because the state-dependent form (LTC, CfC)
  has to run token by token and is too slow for the laptop.
- Fast: fast weights. Inside one context the layer writes key-value associations into a matrix
  as the tokens go (a Hebbian outer product that slowly decays) and reads them back. They live
  only as long as the text in the context, then they are gone.
- Hopfield: a modern Hopfield memory. Learned patterns are recalled by similarity in two
  retrieval steps, so a partial cue settles toward a whole stored pattern.
- Dendrites: a feed-forward layer with active dendrites. A context vector (the mean of the text
  so far) is read by several dendrite segments per group of neurons; the strongest segment
  opens or closes the group, so different conversations use different neurons.

What each part is worth is decided by the exam, not by its name.
"""

CHUNK = 8        # scan in chunks: within 8 steps of forgetting at most e^-1 per step, float32 stays exact
STATE = 4        # state size per channel of the ssm mixer
STEP_MIN = -1.0  # fastest forgetting per token, in log units


def scan(torch, log_decay, inputs):
    """h_t = exp(log_decay_t) * h_{t-1} + inputs_t over dimension 1, in float32."""
    log_decay, inputs = log_decay.float().clamp(min=STEP_MIN, max=0.0), inputs.float()
    out, h = [], torch.zeros_like(inputs[:, 0])
    for s in range(0, inputs.shape[1], CHUNK):
        cum = log_decay[:, s:s + CHUNK].cumsum(1)
        inner = (inputs[:, s:s + CHUNK] * torch.exp(-cum)).cumsum(1)
        part = torch.exp(cum) * (h.unsqueeze(1) + inner)
        out.append(part)
        h = part[:, -1]
    return torch.cat(out, 1)


def build(torch, nn, F, width, heads):
    class Scan(nn.Module):
        def __init__(self, liquid=False):
            super().__init__()
            self.liquid = liquid
            self.inp = nn.Linear(width, width * 2, bias=False)
            self.conv = nn.Conv1d(width, width, 4, groups=width, padding=3)
            self.dt = nn.Linear(width, width)
            if liquid:
                self.target = nn.Linear(width, width)
            else:
                self.a_log = nn.Parameter(torch.log(torch.arange(1, STATE + 1).float()).repeat(width, 1))
                self.bc = nn.Linear(width, STATE * 2, bias=False)
                self.skip = nn.Parameter(torch.ones(width))
            self.out = nn.Linear(width, width, bias=False)
            nn.init.zeros_(self.out.weight)

        def forward(self, x):
            b, n, _ = x.shape
            u, z = self.inp(x).chunk(2, -1)
            u = F.silu(self.conv(u.transpose(1, 2))[..., :n].transpose(1, 2))
            dt = F.softplus(self.dt(u)).float()
            if self.liquid:
                # Each channel moves toward its target at an input-dependent speed.
                decay = -dt
                y = scan(torch, decay, (1 - torch.exp(decay.clamp(min=STEP_MIN))) * torch.tanh(self.target(u)).float())
            else:
                bx, cx = self.bc(u).float().chunk(2, -1)
                decay = -dt.unsqueeze(-1) * torch.exp(self.a_log.float())
                drive = dt.unsqueeze(-1) * bx.unsqueeze(2) * u.float().unsqueeze(-1)
                h = scan(torch, decay.reshape(b, n, -1), drive.reshape(b, n, -1)).reshape(b, n, width, STATE)
                y = (h * cx.unsqueeze(2)).sum(-1) + self.skip * u.float()
            return self.out((y * F.silu(z.float())).to(x.dtype))

    class Fast(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(width)
            self.qkv = nn.Linear(width, width * 3, bias=False)
            self.decay = nn.Parameter(torch.full((heads,), 3.0))  # forget factor sigmoid(3) ≈ 0.95 a token
            self.out = nn.Linear(width, width, bias=False)
            nn.init.zeros_(self.out.weight)

        def forward(self, x):
            b, n, _ = x.shape
            q, k, v = (t.reshape(b, n, heads, -1).transpose(1, 2) for t in self.qkv(self.norm(x)).chunk(3, -1))
            q, k = F.elu(q) + 1, F.elu(k) + 1
            t = torch.arange(n, device=x.device)
            gap = (t.unsqueeze(1) - t.unsqueeze(0)).float()
            keep = F.logsigmoid(self.decay.float()).reshape(heads, 1, 1) * gap.clamp(min=0)
            # Weight written at token s, read at token t: decayed outer product, causal.
            weights = (q.float() @ k.float().transpose(-1, -2)) * torch.exp(keep).masked_fill(gap < 0, 0.0)
            y = (weights @ v.float()) / (weights.sum(-1, keepdim=True) + 1e-6)
            return x + self.out(y.transpose(1, 2).reshape(b, n, width).to(x.dtype))

    class Hopfield(nn.Module):
        def __init__(self, slots):
            super().__init__()
            self.norm = nn.LayerNorm(width)
            self.patterns = nn.Parameter(torch.randn(slots, width) * width ** -0.5)
            self.beta = nn.Parameter(torch.tensor(float(width) ** 0.5))
            self.out = nn.Linear(width, width, bias=False)
            nn.init.zeros_(self.out.weight)

        def forward(self, x):
            xi = self.norm(x)
            for _ in range(2):
                scores = (self.beta * xi @ self.patterns.t() / width).softmax(-1)
                xi = scores @ self.patterns
            if getattr(self, "trace", None) is not None:
                self.trace += scores.reshape(-1, scores.shape[-1]).sum(0).detach().cpu()
            return x + self.out(xi)

    class Dendrites(nn.Module):
        def __init__(self, segments):
            super().__init__()
            self.up = nn.Linear(width, width * 4)
            self.down = nn.Linear(width * 4, width)
            nn.init.zeros_(self.down.weight)
            nn.init.zeros_(self.down.bias)
            self.segments = segments
            self.seg = nn.Linear(width, width * segments)  # one gate per group of 4 neurons

        def forward(self, x):
            n = x.shape[1]
            context = x.cumsum(1) / torch.arange(1, n + 1, device=x.device, dtype=x.dtype).reshape(1, n, 1)
            gate = torch.sigmoid(self.seg(context).reshape(*x.shape[:2], width, self.segments).amax(-1))
            return self.down(F.gelu(self.up(x)) * gate.repeat_interleave(4, -1))

    return {"Scan": Scan, "Fast": Fast, "Hopfield": Hopfield, "Dendrites": Dendrites}
