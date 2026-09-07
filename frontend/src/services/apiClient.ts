import type { APIResponse } from '../types';

/**
 * API client for SD-Automation
 * Communicates with Python FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class APIClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    timeoutMs: number = 30000
  ): Promise<APIResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = {
      ...options.headers,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      clearTimeout(timeoutId);
      return {
        success: false,
        error: {
          code: 'API_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error occurred',
        },
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Upload PDF file for OCR extraction
   * Uses extended timeout (5 minutes) for Gemini AI processing
   */
  async uploadPDF(file: File): Promise<APIResponse<{ extractionId: string; status: string }>> {
    const formData = new FormData();
    formData.append('file', file);

    // 5 minute timeout for AI extraction
    return this.request('/extract', {
      method: 'POST',
      body: formData,
    }, 300000);
  }

  /**
   * Get extracted data from uploaded PDF
   */
  async getExtractedData(extractionId: string): Promise<
    APIResponse<{
      poNumber: string;
      poDate: string;
      vendor: { name: string; number: string };
      lineItems: Array<{
        lineNumber: string;
        materialDescription: string;
        quantity: number;
        unitOfMeasure: string;
        unitPrice: number;
        totalPrice: number;
      }>;
      totalAmount?: number;
      currency?: string;
      rawText: string;
      rawJSON: Record<string, unknown>;
      orders?: Array<{
        poIndex: number;
        poNumber: string;
        header: Array<{
          field: string;
          table: string;
          description: string;
          value: string;
          status: string;
          notes: string;
        }>;
        lineItems: Array<{
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
        }>;
      }>;
    }>
  > {
    return this.request(`/extract/${extractionId}`, {
      method: 'GET',
    });
  }

  /**
   * Get mapping suggestions based on extracted data
   */
  async getMappingData(extractionId: string): Promise<
    APIResponse<{
      mappings: Array<{
        poNumber: string;
        lineNumber: string;
        materialNumber: string;
        materialDescription: string;
        quantity: number;
        unitOfMeasure: string;
        unitPrice: number;
        totalPrice: number;
        suggestedSoldTo: string;
        suggestedShipTo: string;
        pricingDate: string;
        matchScore: number;
        status: string;
      }>;
    }>
  > {
    return this.request(`/mapping/suggest/${extractionId}`, {
      method: 'GET',
    });
  }

  /**
   * Validate mapping data before sending to SAP
   */
  async validateMapping(mappingData: unknown): Promise<
    APIResponse<{
      isValid: boolean;
      errors: Array<{ field: string; message: string }>;
    }>
  > {
    return this.request('/mapping/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mappingData),
    });
  }

  /**
   * Push validated data to SAP backend
   */
  async pushToSAP(salesOrderData: unknown): Promise<
    APIResponse<{
      sapOrderNumber: string;
      status: string;
    }>
  > {
    return this.request('/sap/create-order', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(salesOrderData),
    });
  }

  /**
   * Get master data (materials, customers, vendors)
   */
  async getMasterData(type: 'materials' | 'customers' | 'vendors'): Promise<
    APIResponse<{
      data: Array<Record<string, unknown>>;
    }>
  > {
    return this.request(`/master-data/${type}`, {
      method: 'GET',
    });
  }
}

export const apiClient = new APIClient();
