from citycouncil.config import Settings
from citycouncil.ingest.hf_embedding_params import hf_feature_extraction_call_kwargs


def test_hf_feature_extraction_call_kwargs_query_vs_chunk() -> None:
    s = Settings.model_construct(
        huggingface_token="t",
        huggingface_embedding_model="m",
        embedding_dimensions=384,
        huggingface_normalize_embeddings=True,
        huggingface_prompt_name="document",
        huggingface_search_prompt_name="query",
        embed_input_max_chars=12000,
        huggingface_inference_base_url="https://router.huggingface.co/hf-inference",
    )
    c = hf_feature_extraction_call_kwargs(s, for_query=False)
    q = hf_feature_extraction_call_kwargs(s, for_query=True)
    assert c["prompt_name"] == "document"
    assert q["prompt_name"] == "query"
    assert c["model"] == "m"
