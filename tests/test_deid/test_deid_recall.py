"""Regression test: the de-identifier must achieve 100% PHI recall on
labeled synthetic referrals (ground truth = stress-generator manifest)."""

from deid.eval_deid import run_eval


def test_native_pdfs_have_zero_phi_leaks(tmp_path):
    summary = run_eval(count=4, seed=20260831, profiles=("native",),
                       include_scans=False, workdir=tmp_path)
    assert summary["documents_evaluated"] >= 4
    assert summary["per_type"]["patient_name"]["total"] >= 4
    assert summary["overall"] == "PASS", summary["failures"]
    for etype, counts in summary["per_type"].items():
        if counts["total"]:
            assert counts["recall"] == 1.0, (etype, counts)
