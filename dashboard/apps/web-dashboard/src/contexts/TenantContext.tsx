import React, { createContext, useContext, useState, useEffect } from "react";
import { OperatingCompany, MineSite } from "@subsense/shared";
import { fetchApi } from "../services/api";
import { useAuth } from "./AuthContext";

interface TenantContextType {
  currentTenantId: string;
  setCurrentTenantId: (id: string) => void;
  currentSiteId: string;
  setCurrentSiteId: (id: string) => void;
  availableTenants: OperatingCompany[];
  availableSites: MineSite[];
  refreshSites: () => Promise<void>;
  isLoading: boolean;
}

const DEFAULT_TENANTS: OperatingCompany[] = [
  {
    id: "OPCO-ECL-01",
    jurisdiction_id: "JUR-DGMS-EAST",
    name: "Eastern Coalfields Limited",
    short_code: "ECL",
  },
  {
    id: "OPCO-BCCL-02",
    jurisdiction_id: "JUR-DGMS-EAST",
    name: "Bharat Coking Coal Limited",
    short_code: "BCCL",
  },
];

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const TenantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser } = useAuth();
  const [currentTenantId, setCurrentTenantId] = useState<string>(
    currentUser.tenantId || "OPCO-ECL-01"
  );
  const [currentSiteId, setCurrentSiteId] = useState<string>("PANEL7-JHARIA");
  const [availableTenants, setAvailableTenants] = useState<OperatingCompany[]>(DEFAULT_TENANTS);
  const [availableSites, setAvailableSites] = useState<MineSite[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Sync tenant when user changes unless user is regulator
  useEffect(() => {
    if (currentUser.tenantId && currentUser.role !== "dgms_regulator") {
      setCurrentTenantId(currentUser.tenantId);
    }
  }, [currentUser]);

  const refreshSites = async () => {
    setIsLoading(true);
    try {
      const res = await fetchApi(`/tenants/${currentTenantId}/sites`, {
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });
      if (res.sites && res.sites.length > 0) {
        setAvailableSites(res.sites);
        // If current site not in list, select first
        if (!res.sites.some((s: any) => s.id === currentSiteId)) {
          setCurrentSiteId(res.sites[0].id);
        }
      }
    } catch (err) {
      console.warn("Failed to load sites from API, using fallback defaults:", err);
      // Fallback
      if (currentTenantId === "OPCO-ECL-01") {
        setAvailableSites([
          {
            id: "PANEL7-JHARIA",
            tenant_id: "OPCO-ECL-01",
            name: "Jharia Seam 7 Subsidence Sector",
            status: "active",
            node_ids: ["SS-PANEL7-N042", "SS-PANEL7-N043", "SS-PANEL7-N044", "SS-PANEL7-N045"],
            gateway_credentials: { gateway_eui: "GW-ECL-JH-007", protocol: "sub_ghz_mesh" },
            seam_depth_meters: 240,
            extraction_method: "bord_and_pillar",
            boundaries_geojson: {},
            s3_report_prefix: "/tenants/OPCO-ECL-01/PANEL7-JHARIA/reports/",
            created_at: new Date().toISOString(),
          },
          {
            id: "RANIGANJ-SEAM-4",
            tenant_id: "OPCO-ECL-01",
            name: "Raniganj Seam 4 Longwall Sector",
            status: "active",
            node_ids: ["SS-RANI-N011", "SS-RANI-N012"],
            gateway_credentials: { gateway_eui: "GW-ECL-RN-004", protocol: "lorawan_v1.0.4" },
            seam_depth_meters: 310,
            extraction_method: "longwall",
            boundaries_geojson: {},
            s3_report_prefix: "/tenants/OPCO-ECL-01/RANIGANJ-SEAM-4/reports/",
            created_at: new Date().toISOString(),
          },
        ]);
      } else {
        setAvailableSites([
          {
            id: "MOONIDIH-SEAM-16",
            tenant_id: "OPCO-BCCL-02",
            name: "Moonidih Underground Deep Seam 16",
            status: "active",
            node_ids: ["SS-MOON-N101", "SS-MOON-N102"],
            gateway_credentials: { gateway_eui: "GW-BCCL-MN-016", protocol: "sub_ghz_mesh" },
            seam_depth_meters: 450,
            extraction_method: "longwall",
            boundaries_geojson: {},
            s3_report_prefix: "/tenants/OPCO-BCCL-02/MOONIDIH-SEAM-16/reports/",
            created_at: new Date().toISOString(),
          },
        ]);
        setCurrentSiteId("MOONIDIH-SEAM-16");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshSites();
  }, [currentTenantId]);

  return (
    <TenantContext.Provider
      value={{
        currentTenantId,
        setCurrentTenantId,
        currentSiteId,
        setCurrentSiteId,
        availableTenants,
        availableSites,
        refreshSites,
        isLoading,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = (): TenantContextType => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
};
