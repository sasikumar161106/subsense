import numpy as np
from PIL import Image, ImageDraw, ImageFont

class StalenessDecorator:
    """
    SubSense Staleness Decorator (Section 5.1 & Section 5.5).
    Applies prominent diagonal warning watermark stripes across outdated gateway zones
    when data currency exceeds the 30-second SLA.
    """
    AMBER_STRIPE_COLOR = (245, 158, 11, 115)  # rgba(245, 158, 11, 0.45)
    STRIPE_WIDTH_PX = 8
    STRIPE_SPACING_PX = 24

    @classmethod
    def apply_staleness_stripes(
        cls,
        rgba_image: np.ndarray,
        currency_age_seconds: float,
        staleness_threshold_seconds: float = 30.0
    ) -> np.ndarray:
        """
        Overlays diagonal hazard stripes if currency_age_seconds > staleness_threshold_seconds.
        """
        if currency_age_seconds <= staleness_threshold_seconds:
            return rgba_image

        H, W, _ = rgba_image.shape
        pil_img = Image.fromarray(rgba_image, mode="RGBA")
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw 45-degree diagonal stripes
        diag_total = H + W
        for offset in range(-H, diag_total, cls.STRIPE_SPACING_PX):
            draw.line(
                [(offset, 0), (offset + H, H)],
                fill=cls.AMBER_STRIPE_COLOR,
                width=cls.STRIPE_WIDTH_PX
            )

        # Composite overlay onto base image
        result_pil = Image.alpha_composite(pil_img, overlay)
        return np.array(result_pil, dtype=np.uint8)
