import { create } from 'zustand';
import type { PurchaseOrderExtracted, SalesOrderMapping } from '../types';

interface MappingState {
  // Current PO being processed
  currentPurchaseOrder: PurchaseOrderExtracted | null;
  setCurrentPurchaseOrder: (po: PurchaseOrderExtracted | null) => void;

  // Mapped sales order rows
  mappingRows: SalesOrderMapping[];
  setMappingRows: (rows: SalesOrderMapping[]) => void;
  updateMappingRow: (lineNumber: string, updates: Partial<SalesOrderMapping>) => void;
  addMappingRow: (row: SalesOrderMapping) => void;
  removeMappingRow: (lineNumber: string) => void;

  // Vendor/Customer master data
  vendorMasterData: Array<{ id: string; name: string; number: string }>;
  setVendorMasterData: (data: Array<{ id: string; name: string; number: string }>) => void;

  // Customer/Party master data for sold-to and ship-to parties
  partyMasterData: Array<{ id: string; name: string; number: string }>;
  setPartyMasterData: (data: Array<{ id: string; name: string; number: string }>) => void;

  // Material master data for validation
  materialMasterData: Array<{ materialNumber: string; description: string }>;
  setMaterialMasterData: (data: Array<{ materialNumber: string; description: string }>) => void;

  // Track unsaved changes
  hasUnsavedChanges: boolean;
  setHasUnsavedChanges: (hasChanges: boolean) => void;

  // Clear all state
  reset: () => void;
}

export const useMappingStore = create<MappingState>((set) => ({
  currentPurchaseOrder: null,
  setCurrentPurchaseOrder: (po) => set({ currentPurchaseOrder: po }),

  mappingRows: [],
  setMappingRows: (rows) => set({ mappingRows: rows, hasUnsavedChanges: false }),

  updateMappingRow: (lineNumber, updates) =>
    set((state) => ({
      mappingRows: state.mappingRows.map((row) =>
        row.lineNumber === lineNumber ? { ...row, ...updates } : row
      ),
      hasUnsavedChanges: true,
    })),

  addMappingRow: (row) =>
    set((state) => ({
      mappingRows: [...state.mappingRows, row],
      hasUnsavedChanges: true,
    })),

  removeMappingRow: (lineNumber) =>
    set((state) => ({
      mappingRows: state.mappingRows.filter((row) => row.lineNumber !== lineNumber),
      hasUnsavedChanges: true,
    })),

  vendorMasterData: [],
  setVendorMasterData: (data) => set({ vendorMasterData: data }),

  partyMasterData: [],
  setPartyMasterData: (data) => set({ partyMasterData: data }),

  materialMasterData: [],
  setMaterialMasterData: (data) => set({ materialMasterData: data }),

  hasUnsavedChanges: false,
  setHasUnsavedChanges: (hasChanges: boolean) => set({ hasUnsavedChanges: hasChanges }),

  reset: () =>
    set({
      currentPurchaseOrder: null,
      mappingRows: [],
      vendorMasterData: [],
      partyMasterData: [],
      materialMasterData: [],
      hasUnsavedChanges: false,
    }),
}));
