import React, { createContext, useContext, useState, useEffect } from "react";
import { UserRole, ROLE_DEFINITIONS, RoleMetadata, hasCapability, Capability } from "@subsense/shared";
import { fetchApi } from "../services/api";

export interface CurrentUser {
  userId: string;
  email: string;
  name: string;
  role: UserRole;
  tenantId: string | null;
  jurisdictionId: string | null;
  mfaVerified: boolean;
}

interface AuthContextType {
  currentUser: CurrentUser;
  roleMetadata: RoleMetadata;
  switchRole: (role: UserRole) => Promise<void>;
  verifyMfa: (token: string) => Promise<boolean>;
  can: (capability: Capability) => boolean;
  isLoading: boolean;
}

const DEFAULT_USER: CurrentUser = {
  userId: "USR-OP-8492",
  email: "operator.ecl@subsense.gov.in",
  name: "Rajesh Kumar",
  role: "mine_operator",
  tenantId: "OPCO-ECL-01",
  jurisdictionId: "JUR-DGMS-EAST",
  mfaVerified: true,
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<CurrentUser>(DEFAULT_USER);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const switchRole = async (newRole: UserRole) => {
    setIsLoading(true);
    try {
      const res = await fetchApi("/auth/login", {
        method: "POST",
        body: JSON.stringify({ role: newRole }),
      });

      if (res.token) {
        localStorage.setItem("subsense_token", res.token);
      }
      setCurrentUser(res.session);
    } catch (err) {
      console.error("Failed to switch role:", err);
      // Fallback local mock switch
      const mockUsers: Record<UserRole, CurrentUser> = {
        mine_operator: {
          userId: "USR-OP-8492",
          email: "operator.ecl@subsense.gov.in",
          name: "Rajesh Kumar (Mine Operator)",
          role: "mine_operator",
          tenantId: "OPCO-ECL-01",
          jurisdictionId: "JUR-DGMS-EAST",
          mfaVerified: true,
        },
        geotech_planner: {
          userId: "USR-GEO-1021",
          email: "geotech.ecl@subsense.gov.in",
          name: "Dr. Ananya Sen (Geotech Planner)",
          role: "geotech_planner",
          tenantId: "OPCO-ECL-01",
          jurisdictionId: "JUR-DGMS-EAST",
          mfaVerified: true,
        },
        dgms_regulator: {
          userId: "USR-REG-4412",
          email: "inspector.dgms@subsense.gov.in",
          name: "S. K. Verma (DGMS Chief Inspector)",
          role: "dgms_regulator",
          tenantId: null, // Jurisdiction wide
          jurisdictionId: "JUR-DGMS-EAST",
          mfaVerified: true,
        },
        site_admin: {
          userId: "USR-ADM-001",
          email: "admin.ecl@subsense.gov.in",
          name: "Vikram Malhotra (Site Administrator)",
          role: "site_admin",
          tenantId: "OPCO-ECL-01",
          jurisdictionId: "JUR-DGMS-EAST",
          mfaVerified: true,
        },
      };
      setCurrentUser(mockUsers[newRole]);
    } finally {
      setIsLoading(false);
    }
  };

  const verifyMfa = async (code: string): Promise<boolean> => {
    try {
      const res = await fetchApi("/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({ userId: currentUser.userId, mfaToken: code }),
      });
      if (res.valid) {
        setCurrentUser((prev) => ({ ...prev, mfaVerified: true }));
        return true;
      }
      return false;
    } catch {
      return false;
    }
  };

  const can = (capability: Capability): boolean => {
    return hasCapability(currentUser.role, capability);
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        roleMetadata: ROLE_DEFINITIONS[currentUser.role],
        switchRole,
        verifyMfa,
        can,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
