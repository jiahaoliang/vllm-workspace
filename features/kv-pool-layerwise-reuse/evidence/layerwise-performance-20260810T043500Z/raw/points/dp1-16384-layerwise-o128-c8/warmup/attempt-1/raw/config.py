from ais_bench.benchmark.calculators import DefaultPerfMetricCalculator
from ais_bench.benchmark.datasets import CustomDataset
from ais_bench.benchmark.models import VLLMCustomAPI
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.partitioners import NaivePartitioner
from ais_bench.benchmark.runners import LocalRunner
from ais_bench.benchmark.summarizers import DefaultPerfSummarizer
from ais_bench.benchmark.tasks import OpenICLApiInferTask

mode = "perf"
summarizer = dict(
    attr="performance",
    type=DefaultPerfSummarizer,
    calculator=dict(
        type=DefaultPerfMetricCalculator,
        stats_list=["Average", "Min", "Max", "Median", "P75", "P90", "P95", "P99"],
    ),
)

models = [dict(
    abbr='layerwise',
    attr="service",
    type=VLLMCustomAPI,
    stream=True,
    retry=1,  # AISBench iterates range(retry); 1 means one total request attempt.
    url='http://vllm-proxy-service:8000/',
    model="vllm-ascend/DeepSeek-V2-Lite-W8A8",
    path="/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8",
    max_out_len=128,
    batch_size=8,
    request_rate=0,
    generation_kwargs=dict(temperature=0, ignore_eos=True),
)]

datasets = [dict(
    type=CustomDataset,
    abbr='layerwise',
    path='/client-tools/runs/dp1-16384-layerwise-o128-c8/warmup/e3f8132189e0421d/dataset.jsonl',
    reader_cfg=dict(input_columns=["question"], output_column="answer"),
    infer_cfg=dict(
        prompt_template=dict(type=PromptTemplate, template="{question}"),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    ),
)]

infer = dict(
    partitioner=dict(type=NaivePartitioner),
    runner=dict(
        type=LocalRunner,
        max_num_workers=8,
        task=dict(type=OpenICLApiInferTask),
    ),
)
work_dir='/client-tools/runs/dp1-16384-layerwise-o128-c8/warmup/e3f8132189e0421d/aisbench-output'
