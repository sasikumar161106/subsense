from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

class DGMSReportExporter:
    """
    SubSense DGMS Statutory Report Exporter (Section 5.3).
    Generates formal high-resolution audit snapshots with regulatory metadata,
    coordinate references, scale rulers, and watermarks for statutory inspections.
    """
    @classmethod
    def compile_audit_report_image(
        cls,
        map_image: Image.Image,
        site_id: str,
        site_name: str,
        vertical_exaggeration: float,
        active_zones: List[Dict[str, Any]],
        as_of_time: Optional[datetime] = None
    ) -> Image.Image:
        now = as_of_time or datetime.now(timezone.utc)
        
        # Expand canvas to include statutory header and footer banners
        W, H = map_image.size
        header_h = 90
        footer_h = 70
        total_w = W
        total_h = H + header_h + footer_h

        report_img = Image.new("RGBA", (total_w, total_h), (24, 28, 36, 255))
        draw = ImageDraw.Draw(report_img)

        # Paste base rendered map
        report_img.paste(map_image, (0, header_h))

        # 1. Header Banner
        draw.rectangle([(0, 0), (total_w, header_h)], fill=(15, 23, 42, 255))
        draw.text((20, 15), f"SUBSENSE GEOTECHNICAL MONITORING REPORT — {site_id}", fill=(241, 245, 249, 255))
        draw.text((20, 38), f"Concession: {site_name} | Compliance Standard: DGMS Tech Circular Baseline", fill=(148, 163, 184, 255))
        draw.text((20, 60), f"Generated: {now.strftime('%Y-%m-%d %H:%M:%SZ')} | Exaggeration: {int(vertical_exaggeration)}X", fill=(245, 158, 11, 255))

        # 2. Permanent Scale Ruler Watermark on Canvas
        draw.rectangle([(20, header_h + 20), (380, header_h + 60)], fill=(0, 0, 0, 180))
        draw.text((30, header_h + 28), f"VERTICAL EXAGGERATION: {int(vertical_exaggeration)}X (DGMS AUDIT)", fill=(245, 158, 11, 255))

        # 3. Active Zones Summary Box
        zone_str = f"Active Risk Polygons: {len(active_zones)}"
        draw.rectangle([(total_w - 280, header_h + 20), (total_w - 20, header_h + 60)], fill=(0, 0, 0, 180))
        draw.text((total_w - 270, header_h + 28), zone_str, fill=(239, 68, 68, 255))

        # 4. Statutory Footer
        draw.rectangle([(0, total_h - footer_h), (total_w, total_h)], fill=(15, 23, 42, 255))
        disclaimer = "CONFIDENTIAL: DGMS Statutory Audit Record. Spatial coordinates reprojected to UTM Zone 45N."
        draw.text((20, total_h - footer_h + 15), disclaimer, fill=(148, 163, 184, 255))
        draw.text((20, total_h - footer_h + 38), "Certified by SubSense Layer 5 Spatial Architecture v2.1", fill=(100, 116, 139, 255))

        return report_img
