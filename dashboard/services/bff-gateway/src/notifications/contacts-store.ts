export interface EmergencyContact {
  id: string;
  name: string;
  role: string;
  phoneNumber: string;
  isActive: boolean;
  createdAt: string;
}

const DEFAULT_CONTACTS: EmergencyContact[] = [
  {
    id: "cnt-01",
    name: "Mine Safety Officer (Termux)",
    role: "Emergency Response Lead",
    phoneNumber: "+917358160485",
    isActive: true,
    createdAt: new Date().toISOString(),
  },
  {
    id: "cnt-02",
    name: "Pit-Head Supervisor",
    role: "On-Duty Overman",
    phoneNumber: "+917010336893",
    isActive: true,
    createdAt: new Date().toISOString(),
  },
];

export class EmergencyContactsStore {
  private static contacts: EmergencyContact[] = [...DEFAULT_CONTACTS];

  static getAll(): EmergencyContact[] {
    return [...this.contacts];
  }

  static getActive(): EmergencyContact[] {
    return this.contacts.filter((c) => c.isActive);
  }

  static add(data: { name: string; role: string; phoneNumber: string; isActive?: boolean }): EmergencyContact {
    const newContact: EmergencyContact = {
      id: `cnt-${Date.now().toString(36)}`,
      name: data.name.trim(),
      role: data.role.trim() || "Miner / Safety Staff",
      phoneNumber: data.phoneNumber.trim(),
      isActive: data.isActive ?? true,
      createdAt: new Date().toISOString(),
    };
    this.contacts.push(newContact);
    return newContact;
  }

  static update(id: string, updates: Partial<EmergencyContact>): EmergencyContact | null {
    const idx = this.contacts.findIndex((c) => c.id === id);
    if (idx === -1) return null;
    this.contacts[idx] = { ...this.contacts[idx], ...updates };
    return this.contacts[idx];
  }

  static delete(id: string): boolean {
    const prevLen = this.contacts.length;
    this.contacts = this.contacts.filter((c) => c.id !== id);
    return this.contacts.length < prevLen;
  }

  static resetToDefault(): EmergencyContact[] {
    this.contacts = [...DEFAULT_CONTACTS];
    return [...this.contacts];
  }
}
