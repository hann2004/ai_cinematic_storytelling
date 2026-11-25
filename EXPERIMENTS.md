# Experiments

## 1. Cloudflare FLUX seed support

- **Hypothesis:** The FLUX REST endpoint accepts a fixed `seed` parameter, as shown in the model documentation example.
- **Change:** Sent one image request with `seed: 42`, then removed the field after the API rejected it.
- **Result:** The live endpoint returned error 5006 (`Additional or unevaluated properties '/seed' ... not allowed`). A request without `seed` succeeded and generated `outputs/smoke/flux_schnell.jpg`.
- **Decision:** Omit the seed for this endpoint unless its live schema later confirms support.