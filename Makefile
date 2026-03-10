CONDA_ENV ?= SmartRAG
PYTHONPATH_VAR ?= PYTHONPATH=.
TEAM_ID ?= team_test
INPUT_DIR ?= data/raw/phase1_samples
PATTERNS ?= *.md
RETRIEVAL_MODE ?= vector
RESULT_CSV ?= eval/phase2_baseline/results_latest.csv
SUMMARY_MD ?= eval/phase2_baseline/summary_latest.md

.PHONY: help ingest eval summary summary-phase3 test test-integration test-query test-health chroma-peek run-rag-api run-agent-ui

help:
	@echo "可用命令:"
	@echo "  make ingest             # 批量入库 phase1 样本文档"
	@echo "  make eval               # 运行评测（可用 TEAM_ID/RETRIEVAL_MODE/RESULT_CSV 覆盖）"
	@echo "  make summary            # 汇总评测结果（可用 RESULT_CSV/SUMMARY_MD 覆盖）"
	@echo "  make summary-phase3     # 批量汇总 phase3 三种模式结果"
	@echo "  make test               # 运行全部 integration 测试"
	@echo "  make test-integration   # 同 test"
	@echo "  make test-query         # 仅运行 query 相关测试"
	@echo "  make test-health        # 仅运行 health 测试"
	@echo "  make chroma-peek TEAM=team_test  # 查看指定团队的 Chroma 数据样本"
	@echo "  make run-rag-api        # 启动 RAG FastAPI 服务"
	@echo "  make run-agent-ui       # 启动独立 LangChain Agent Chat UI"

ingest:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/batch_ingest.py \
		--team-id $(TEAM_ID) \
		--input-dir $(INPUT_DIR) \
		--patterns "$(PATTERNS)" \
		--recursive

eval:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/run_eval.py \
		--team-id-override $(TEAM_ID) \
		--retrieval-mode $(RETRIEVAL_MODE) \
		--output $(RESULT_CSV)

summary:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/summarize_eval.py \
		--input $(RESULT_CSV) \
		--output-md $(SUMMARY_MD)

summary-phase3:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/summarize_eval.py \
		--input eval/phase3_hybrid/results_vector.csv \
		--output-md eval/phase3_hybrid/summary_vector.md
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/summarize_eval.py \
		--input eval/phase3_hybrid/results_hybrid.csv \
		--output-md eval/phase3_hybrid/summary_hybrid.md
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/summarize_eval.py \
		--input eval/phase3_hybrid/results_hybrid_rerank.csv \
		--output-md eval/phase3_hybrid/summary_hybrid_rerank.md

test: test-integration

test-integration:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) pytest -q tests/integration

test-query:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) pytest -q tests/integration/test_query_api.py

test-health:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) pytest -q tests/integration/test_health.py

chroma-peek:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) python scripts/chroma_peek.py --team-id $(TEAM)

run-rag-api:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-agent-ui:
	conda run -n $(CONDA_ENV) env $(PYTHONPATH_VAR) \
		STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
		STREAMLIT_SERVER_HEADLESS=true \
		streamlit run agent_app/chat_ui.py --server.port 8501
