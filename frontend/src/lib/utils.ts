import type { ValidationError } from '../types';
import { ZodError } from 'zod';

/**
 * Utility functions for SD-Automation
 */

/**
 * Format Zod validation errors into user-friendly messages
 */
export const formatZodErrors = (error: ZodError): ValidationError[] => {
  return error.issues.map((err) => ({
    field: err.path.join('.'),
    message: err.message,
    severity: err.code === 'invalid_type' ? 'error' : 'warning',
  }));
};

/**
 * Highlight cells with validation errors
 */
export const getValidationStyle = (severity: 'warning' | 'error' | 'info'): string => {
  switch (severity) {
    case 'error':
      return 'bg-red-100 border border-red-400 text-red-900';
    case 'warning':
      return 'bg-yellow-100 border border-yellow-400 text-yellow-900';
    case 'info':
      return 'bg-blue-100 border border-blue-400 text-blue-900';
    default:
      return '';
  }
};

/**
 * Format currency for display
 */
export const formatCurrency = (value: number, currency: string = 'USD'): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value);
};

/**
 * Format date for SAP (typically YYYY-MM-DD)
 */
export const formatDateForSAP = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Parse date from various formats
 */
export const parseDate = (dateString: string): Date | null => {
  const date = new Date(dateString);
  return isNaN(date.getTime()) ? null : date;
};

/**
 * Validate material number format (SAP Material ID)
 */
export const isValidMaterialNumber = (materialNumber: string): boolean => {
  return /^\d{8,18}$/.test(materialNumber.trim());
};

/**
 * Validate party number format (KUNNR/Vendor ID in SAP)
 */
export const isValidPartyNumber = (partyNumber: string): boolean => {
  return /^\d{1,10}$/.test(partyNumber.trim());
};

/**
 * Generate unique ID for tracking
 */
export const generateId = (prefix: string = ''): string => {
  return `${prefix}${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Debounce function for form inputs
 */
export const debounce = <T extends (...args: unknown[]) => void>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: ReturnType<typeof setTimeout>;

  return function debounced(...args: Parameters<T>) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
};

/**
 * Check if file is a supported upload format
 */
export const isSupportedUploadFile = (file: File): boolean => {
  const name = file.name.toLowerCase()
  return (
    file.type === 'application/pdf' ||
    file.type.startsWith('image/') ||
    name.endsWith('.pdf') ||
    name.endsWith('.png') ||
    name.endsWith('.jpg') ||
    name.endsWith('.jpeg') ||
    name.endsWith('.webp')
  )
};

/**
 * Format file size for display
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};
