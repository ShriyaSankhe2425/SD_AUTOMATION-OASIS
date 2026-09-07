/**
 * Core domain types for SD-Automation PO to SAP Sales Order transformation
 */

export interface PurchaseOrderExtracted {
  id: string;
  fileName: string;
  fileUrl?: string;
  uploadedAt: Date;
  extractedText: string;
  extractedJSON: PurchaseOrderData;
  status: 'pending' | 'processing' | 'completed' | 'error';
  errorMessage?: string;
}

export interface PurchaseOrderData {
  poNumber: string;
  poDate: string;
  vendor: {
    name: string;
    number?: string;
    address?: string;
  };
  lineItems: PurchaseOrderLineItem[];
  totalAmount?: number;
  currency?: string;
  deliveryDate?: string;
  paymentTerms?: string;
  orders?: ReviewOrder[];
}

export interface ReviewHeaderRow {
  field: string;
  table: string;
  description: string;
  value: string;
  status: string;
  notes: string;
}

export interface ReviewLineItemRow {
  lineNumber: string;
  poDescription: string;
  matnr: string;
  matchScore: number;
  quantity: number;
  unit: string;
  unitPrice: number;
  totalPrice: number;
  deliveryDate: string;
  status: string;
}

export interface ReviewOrder {
  poIndex: number;
  poNumber: string;
  header: ReviewHeaderRow[];
  lineItems: ReviewLineItemRow[];
}

export interface PurchaseOrderLineItem {
  lineNumber: string;
  materialNumber?: string;
  materialDescription: string;
  quantity: number;
  unitOfMeasure: string;
  unitPrice?: number;
  totalPrice?: number;
}

export interface SalesOrderMapping extends PurchaseOrderLineItem {
  poNumber: string;
  materialNumber: string; // Required for SAP
  soldToParty: {
    value: string;
    label: string;
  };
  shipToParty: {
    value: string;
    label: string;
  };
  pricingDate: Date;
  validationStatus: ValidationStatus;
  validationErrors: ValidationError[];
}

export interface ValidationStatus {
  isValid: boolean;
  severity: 'info' | 'warning' | 'error';
  message?: string;
}

export interface ValidationError {
  field: string;
  message: string;
  severity: 'warning' | 'error';
}

export interface SalesOrderPayload {
  poNumber: string;
  poDate: string;
  vendorNumber: string;
  lineItems: SalesOrderLineItem[];
}

export interface SalesOrderLineItem {
  lineNumber: string;
  materialNumber: string;
  quantity: number;
  unitOfMeasure: string;
  unitPrice: number;
  soldToParty: string;
  shipToParty: string;
  pricingDate: string;
}

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  timestamp: string;
}
