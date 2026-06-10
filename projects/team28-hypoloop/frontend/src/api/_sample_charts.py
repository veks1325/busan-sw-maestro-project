"""데모용 샘플 보고서 이미지 생성.

실제 서비스에서는 에이전트가 가설 하위 img/ 디렉토리에 PNG를 저장하고,
백엔드가 그 바이트를 report_images로 넘겨준다. mock에서는 같은 모양을
matplotlib로 즉석 생성해 동작을 보여준다(matplotlib 없으면 빈 dict).
"""
from __future__ import annotations

from typing import Dict


def make_report_images(seed: int = 42) -> Dict[str, bytes]:
    try:
        import io
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return {}

    rng = np.random.default_rng(seed)
    imgs: Dict[str, bytes] = {}

    def save(fig) -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=92, bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    # 1) 타깃(SalePrice) 분포 — 원본 vs log1p
    target = rng.lognormal(mean=12, sigma=0.4, size=2000)
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
    ax[0].hist(target, bins=40, color="#4f6bed")
    ax[0].set_title("SalePrice (raw, right-skewed)")
    ax[1].hist(np.log1p(target), bins=40, color="#2f9e6e")
    ax[1].set_title("log1p(SalePrice)")
    imgs["img/target_distribution.png"] = save(fig)

    # 2) 상위 왜도 피처
    feats = ["MiscVal", "PoolArea", "LotArea", "3SsnPorch", "LowQualFinSF",
             "KitchenAbvGr", "BsmtFinSF2", "ScreenPorch", "EnclosedPorch",
             "MasVnrArea"]
    skew = sorted(rng.uniform(1.5, 12.0, size=len(feats)), reverse=True)
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.barh(feats[::-1], skew[::-1], color="#e0922e")
    ax.set_title("Top skewed features")
    ax.set_xlabel("skewness")
    imgs["img/skewed_features.png"] = save(fig)

    # 3) 피처 변환 예시 — 원본 vs log1p
    x = rng.lognormal(mean=2, sigma=1.0, size=1500)
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
    ax[0].hist(x, bins=40, color="#4f6bed")
    ax[0].set_title("Original")
    ax[1].hist(np.log1p(x), bins=40, color="#2f9e6e")
    ax[1].set_title("After log1p")
    imgs["img/example_feature_transformation.png"] = save(fig)

    return imgs
