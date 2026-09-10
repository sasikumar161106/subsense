from typing import Literal
import numpy as np
from scipy.optimize import curve_fit

class SemivariogramModel:
    """
    Theoretical Semivariogram Model for Spatial Autocorrelation (Section 6.2).
    Models spatial variance as a function of lag distance h:
    - Exponential: gamma(h) = c0 + c * (1 - exp(-3 * h / a))
    - Spherical: gamma(h) = c0 + c * (1.5 * (h/a) - 0.5 * (h/a)^3) for h <= a, else c0 + c
    - Gaussian: gamma(h) = c0 + c * (1 - exp(-3 * (h/a)^2))
    """

    def __init__(
        self,
        model_type: Literal["exponential", "spherical", "gaussian"] = "exponential",
        nugget: float = 0.05,
        sill: float = 1.0,
        range_m: float = 250.0,
    ):
        self.model_type = model_type
        self.nugget = nugget
        self.sill = sill
        self.range_m = range_m

    def evaluate(self, h: np.ndarray) -> np.ndarray:
        """Evaluates gamma(h) for given lag distances in meters."""
        h = np.maximum(0.0, h)
        c0 = self.nugget
        c = max(1e-4, self.sill - self.nugget)
        a = max(1.0, self.range_m)

        if self.model_type == "exponential":
            return np.where(h == 0.0, 0.0, c0 + c * (1.0 - np.exp(-3.0 * h / a)))
        elif self.model_type == "spherical":
            ratio = np.clip(h / a, 0.0, 1.0)
            sph = c0 + c * (1.5 * ratio - 0.5 * (ratio ** 3))
            return np.where(h == 0.0, 0.0, np.where(h <= a, sph, c0 + c))
        elif self.model_type == "gaussian":
            return np.where(h == 0.0, 0.0, c0 + c * (1.0 - np.exp(-3.0 * (h / a) ** 2)))
        else:
            return np.where(h == 0.0, 0.0, c0 + c * (1.0 - np.exp(-3.0 * h / a)))

    def fit_from_samples(
        self,
        coords: np.ndarray,  # [N, 2] in UTM meters
        values: np.ndarray,  # [N]
        n_lags: int = 15,
        max_lag: float = 400.0,
    ) -> "SemivariogramModel":
        """Calibrates empirical semivariogram and fits parameters."""
        n = len(values)
        if n < 3:
            return self

        diff_coords = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diff_coords ** 2, axis=-1)).ravel()
        diff_vals = (values[:, np.newaxis] - values[np.newaxis, :]).ravel()
        semivariances = 0.5 * (diff_vals ** 2)

        # Filter positive distances up to max_lag
        valid = (distances > 0.0) & (distances <= max_lag)
        if np.sum(valid) < 5:
            return self

        d_valid = distances[valid]
        g_valid = semivariances[valid]

        # Binning
        bins = np.linspace(0.0, max_lag, n_lags + 1)
        bin_centers = 0.5 * (bins[:-1] + bins[1:])
        bin_gamma = np.zeros(n_lags)

        for i in range(n_lags):
            in_bin = (d_valid >= bins[i]) & (d_valid < bins[i + 1])
            if np.any(in_bin):
                bin_gamma[i] = np.mean(g_valid[in_bin])
            else:
                bin_gamma[i] = np.nan

        valid_bins = ~np.isnan(bin_gamma)
        if np.sum(valid_bins) >= 3:
            try:
                def opt_fn(h, c0, c, a):
                    return np.where(h == 0, 0, c0 + c * (1.0 - np.exp(-3.0 * h / a)))

                popt, _ = curve_fit(
                    opt_fn,
                    bin_centers[valid_bins],
                    bin_gamma[valid_bins],
                    p0=[0.05, float(np.var(values)), 250.0],
                    bounds=([0.0, 0.01, 20.0], [1.0, 5.0, 1000.0]),
                    maxfev=1000,
                )
                self.nugget = float(popt[0])
                self.sill = float(popt[0] + popt[1])
                self.range_m = float(popt[2])
            except Exception:
                pass

        return self
