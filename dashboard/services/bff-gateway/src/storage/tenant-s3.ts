export interface TenantStoragePathConfig {
  bucketName: string;
  tenantId: string;
  siteId: string;
  resourceCategory: "reports" | "point_clouds" | "simulation_runs" | "kriging_grids";
}

export class TenantS3Storage {
  private static defaultBucket = process.env.S3_BUCKET || "subsense-strata-data-production";

  /**
   * Generates strict tenant-isolated S3 key path:
   * /tenants/{tenant_id}/{site_id}/{resource_category}/{filename}
   */
  static getStoragePath(config: TenantStoragePathConfig, filename: string): string {
    const cleanFilename = filename.replace(/^\/+/, "");
    return `tenants/${config.tenantId}/${config.siteId}/${config.resourceCategory}/${cleanFilename}`;
  }

  /**
   * Generates mock signed upload / download URLs with tenant policy enforcement
   */
  static generatePresignedUrl(
    config: TenantStoragePathConfig,
    filename: string,
    operation: "GET" | "PUT" = "GET",
    expiresInSeconds: number = 3600
  ): { s3Key: string; url: string; expiresAt: string } {
    const s3Key = this.getStoragePath(config, filename);
    const expiresAt = new Date(Date.now() + expiresInSeconds * 1000).toISOString();
    const url = `https://${this.defaultBucket}.s3.ap-south-1.amazonaws.com/${s3Key}?X-Amz-Expires=${expiresInSeconds}&tenant_scope=${config.tenantId}`;
    return { s3Key, url, expiresAt };
  }
}
