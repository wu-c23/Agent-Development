Here's how to use the test suite:

  Running Tests

  Run everything (all 773 tests across both projects):
  python -m pytest tests/

  Run a single test file:
  python -m pytest tests/test_data_store.py -q

  Run tests matching a keyword:
  python -m pytest tests/ -k "health" -q

  Run a specific test class or method:
  python -m pytest tests/test_sentiment_api.py::TestHealth -q
  python -m pytest tests/test_data_store.py::TestFallbackData::test_get_novel_by_uid -q

  See failures with full traceback:
  python -m pytest tests/ -q --tb=long

  What Each File Covers

  ┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────┐
  │                File                 │                                Tests for                                 │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_data_store.py                  │ Novel/sentiment data CRUD, fallback loading, search                      │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_rag_engine.py                  │ Chunking, tokenization, TF-IDF retrieval, RAG engine, conversation state │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_sentiment_api.py               │ FastAPI endpoints (health, detail, compare, refresh, chat, KB stats)     │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_sentiment_mock_server.py       │ Mock API server (same endpoints, self-contained mock data)               │
  │ test_rag_engine.py                  │ Chunking, tokenization, TF-IDF retrieval, RAG engine, conversation state │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_sentiment_api.py               │ FastAPI endpoints (health, detail, compare, refresh, chat, KB stats)     │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_sentiment_mock_server.py       │ Mock API server (same endpoints, self-contained mock data)               │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_sentiment_critic_collectors.py │ Review collection, HTML parsing, balanced limiting                       │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_critic.py                      │ Safe-Search's critic.py (score_risks, log parsing)                       │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_safe_search_engine.py          │ Safe-Search engine pipeline                                              │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_safe_search_api.py             │ Safe-Search API endpoints                                                │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_safe_search_*.py (6 files)     │ Config, models, embeddings, vector store, intent, UID utils              │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_review_critic_*.py (3 files)   │ Review critic models, analyzer, collectors                               │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_trend_explorer_api.py          │ Trend Explorer API endpoints                                             │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_trend_fastapi_demo.py          │ FastAPI demo app                                                         │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤
  │ test_agent_client.py                │ Agent client                                                             │
  └─────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘

  Important Note

  These tests use mocked external services (no real API calls). The conftest.py sets fake API keys and timeouts so nothing
  hits DeepSeek or other real endpoints during testing. No source code was modified — all mocking is done in the test
  files.


Here is the tentative result obtained on my(mwh) computer:
================================================== test session starts =================================================== 
platform win32 -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0                                                                
rootdir: C:\Users\lenovo\Desktop\EPSE2L_test\Agent-Development                                                             
plugins: anyio-4.13.0                                                                                                      
collected 773 items                                                                                                        
                                                                                                                           
tests\test_agent_client.py ..........................................                                               [  5%] 
tests\test_critic.py ...........................                                                                    [  8%] 
tests\test_data_store.py ...........................xx..                                                            [ 12%] 
tests\test_intent.py ......................                                                                         [ 15%] 
tests\test_rag_engine.py ..........................................                                                 [ 21%] 
tests\test_review_critic_analyzer.py .........................................................                      [ 28%] 
tests\test_review_critic_collectors.py ..............................................................               [ 36%] 
tests\test_review_critic_models.py ...............................................................                  [ 44%] 
tests\test_safe_search_api.py ..........                                                                            [ 46%] 
tests\test_safe_search_config.py ....................                                                               [ 48%] 
tests\test_safe_search_embeddings.py .....................                                                          [ 51%] 
tests\test_safe_search_engine.py ..........                                                                         [ 52%] 
tests\test_safe_search_mock_server.py .........................................                                     [ 57%] 
tests\test_safe_search_models.py ................................                                                   [ 62%] 
tests\test_sentiment_api.py .............                                                                           [ 63%] 
tests\test_sentiment_critic_collectors.py ..............                                                            [ 65%] 
tests\test_sentiment_mock_server.py ..............                                                                  [ 67%] 
tests\test_trend_explorer_api.py ..........................................                                         [ 72%] 
tests\test_trend_fastapi_demo.py .................................................................................. [ 83%] 
...........................................................................                                         [ 93%] 
tests\test_uid_utils.py ..................                                                                          [ 95%] 
tests\test_vector_store.py ...................................                                                      [100%] 
                                                                                                                           
==================================================== warnings summary ==================================================== 
..\..\..\AppData\Roaming\Python\Python314\site-packages\jieba\_compat.py:18                                                
  C:\Users\lenovo\AppData\Roaming\Python\Python314\site-packages\jieba\_compat.py:18: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
    import pkg_resources

..\..\..\AppData\Roaming\Python\Python314\site-packages\chromadb\telemetry\opentelemetry\__init__.py:128
  C:\Users\lenovo\AppData\Roaming\Python\Python314\site-packages\chromadb\telemetry\opentelemetry\__init__.py:128: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(f):

..\..\..\AppData\Roaming\Python\Python314\site-packages\fastapi\testclient.py:1
  C:\Users\lenovo\AppData\Roaming\Python\Python314\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================================== 771 passed, 2 xfailed, 3 warnings in 21.70s =======================================