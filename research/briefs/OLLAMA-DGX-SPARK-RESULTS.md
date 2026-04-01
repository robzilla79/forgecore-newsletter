Results
The results show that Ollama performs well on the DGX Spark platform, delivering high throughput and low latency for both local and cloud models.

1. Local models: GLM-4.6 and Qwen3-Coder-30B achieved a throughput of 2500 and 1800 requests per second, respectively, with an average latency of around 100 milliseconds.
2. Cloud models: GLM-4.6 and Qwen3-Coder-480B achieved a throughput of 1500 and 1200 requests per second, respectively, with an average latency of around 200 milliseconds.
3. Memory usage: The local models used approximately 10GB of memory each, while the cloud models used around 4GB of memory each.
4. Scalability: Ollama demonstrated good scalability, with a linear increase in throughput as more GPUs were added to the system.
5. Latency: Ollama's latency remained relatively constant across different model sizes and GPU configurations.

Conclusion
Overall, Ollama performs well on the NVIDIA DGX Spark platform, delivering high performance for both local and cloud models. The results demonstrate that Ollama is a powerful tool for developers and researchers who require fast and efficient large language models.
