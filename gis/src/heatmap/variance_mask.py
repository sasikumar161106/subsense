import numpy as np

class VarianceConfidenceMaskEngine:
    """
    SubSense Kriging Estimation Variance Mask Engine (Section 5.1).
    Applies stippling or opacity modulation based on estimation variance sigma_K^2.
    Highlights regions with sparse sensor node coverage where caution is required.
    """
    @classmethod
    def apply_confidence_mask(
        cls,
        rgba_image: np.ndarray,
        variance_grid: np.ndarray,
        variance_threshold: float = 0.25,
        use_stippling: bool = True
    ) -> np.ndarray:
        """
        Modulates alpha channel of RGBA image according to estimation variance.
        If variance > variance_threshold, opacity is reduced, and stipple dots are added.
        """
        result = rgba_image.copy()
        H, W = variance_grid.shape
        
        # Normalized uncertainty factor [0.0 (certain) to 1.0 (highly uncertain)]
        uncertainty = np.clip(variance_grid / (variance_threshold + 1e-6), 0.0, 1.0)
        
        # Opacity attenuation: reduce alpha by up to 50% in uncertain areas
        alpha_scale = 1.0 - 0.5 * uncertainty
        current_alpha = result[:, :, 3].astype(np.float32)
        new_alpha = current_alpha * alpha_scale

        if use_stippling:
            # Generate regular stipple pattern (e.g. 4x4 grid dots)
            y_indices, x_indices = np.indices((H, W))
            stipple_pattern = ((x_indices % 4 == 0) & (y_indices % 4 == 0)) | \
                              ((x_indices % 4 == 2) & (y_indices % 4 == 2))
            
            # Where uncertainty is high (> 0.5), punch tiny stipple holes or darken
            high_uncertainty = (uncertainty > 0.45) & stipple_pattern
            new_alpha[high_uncertainty] = np.maximum(20.0, new_alpha[high_uncertainty] * 0.3)

        result[:, :, 3] = np.clip(new_alpha, 0, 255).astype(np.uint8)
        return result
