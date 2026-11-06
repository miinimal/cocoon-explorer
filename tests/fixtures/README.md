# Test fixtures

`tdx_quote.bin` and `tdx_quote_collateral.json` are the sample TDX quote (v4) and its
Intel PCS collateral from [Phala-Network/dcap-qvl](https://github.com/Phala-Network/dcap-qvl)
(`sample/tdx_quote`, `sample/tdx_quote_collateral.json`, commit
`05c200b752ecb824b73e5b1ae63cc047f1702ab2`), MIT License, Copyright (c) 2026 Phala Network.

The collateral is valid between 2025-06-19 and 2025-07-19, so the tests verify at a fixed
time inside that window.
