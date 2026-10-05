"""Benchmark statistics module — MS8 McNemar / pass@k / ablation tables."""

from noesis.benchmarks.stats import (
    AblationTables,
    BenchSummary,
    CategoryPass1,
    DifficultyRow,
    aggregate_se50_summary,
    generate_ablation_tables,
    main,
    mcnemar_pvalue,
    pass_at_k,
    wilcoxon_signed_rank_pvalue_approx,
)

__all__ = [
    "AblationTables",
    "BenchSummary",
    "CategoryPass1",
    "DifficultyRow",
    "aggregate_se50_summary",
    "generate_ablation_tables",
    "main",
    "mcnemar_pvalue",
    "pass_at_k",
    "wilcoxon_signed_rank_pvalue_approx",
]
