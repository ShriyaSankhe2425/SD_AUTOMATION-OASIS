import { z } from 'zod';

/**
 * Zod validation schemas for SD-Automation
 * Ensures data integrity before sending to SAP backend
 */

// Material Number must be numeric, typically 8-18 digits for SAP
const MaterialNumberSchema = z
  .string()
  .min(1, 'Material Number is required')
  .regex(/^\d+$/, 'Material Number must be numeric')
  .min(8, 'Material Number must be at least 8 digits')
  .max(18, 'Material Number cannot exceed 18 digits');

// Quantity validation
const QuantitySchema = z
  .number()
  .positive('Quantity must be greater than 0')
  .finite('Quantity must be a valid number')
  .multipleOf(0.01, 'Quantity can have at most 2 decimal places');

// Unit of Measure - Dropdown restricted to SAP standard UoMs
const UnitOfMeasureSchema = z.enum(['PC', 'KG', 'L', 'M', 'BOX', 'PALLET']);

// Party number validation (KUNNR in SAP - typically 10 digits)
const PartyNumberSchema = z
  .string()
  .min(1, 'Party is required')
  .regex(/^\d+$/, 'Party number must be numeric')
  .min(1, 'Party number must be at least 1 digit')
  .max(10, 'Party number cannot exceed 10 digits');

// Date validation
const DateSchema = z.date().or(z.string().datetime());

export const SalesOrderLineItemSchema = z.object({
  materialNumber: MaterialNumberSchema,
  quantity: QuantitySchema,
  unitOfMeasure: UnitOfMeasureSchema,
  soldToParty: PartyNumberSchema,
  shipToParty: PartyNumberSchema,
  pricingDate: DateSchema,
  lineNumber: z.string().min(1, 'Line number is required'),
  materialDescription: z.string().optional(),
  unitPrice: z.number().nonnegative('Unit price must be non-negative').optional(),
  totalPrice: z.number().nonnegative('Total price must be non-negative').optional(),
});

export const SalesOrderPayloadSchema = z.object({
  poNumber: z.string().min(1, 'PO Number is required'),
  poDate: z.string().datetime().or(z.date()),
  vendorNumber: z.string().min(1, 'Vendor number is required'),
  lineItems: z.array(SalesOrderLineItemSchema).min(1, 'At least one line item is required'),
});

export const MappingGridRowSchema = z.object({
  lineNumber: z.string(),
  materialNumber: MaterialNumberSchema,
  materialDescription: z.string().optional(),
  quantity: QuantitySchema,
  unitOfMeasure: UnitOfMeasureSchema,
  soldToParty: z.object({
    value: PartyNumberSchema,
    label: z.string(),
  }),
  shipToParty: z.object({
    value: PartyNumberSchema,
    label: z.string(),
  }),
  pricingDate: DateSchema,
  unitPrice: z.number().nonnegative().optional(),
  isEdited: z.boolean().default(false),
});

export type SalesOrderLineItem = z.infer<typeof SalesOrderLineItemSchema>;
export type SalesOrderPayload = z.infer<typeof SalesOrderPayloadSchema>;
export type MappingGridRow = z.infer<typeof MappingGridRowSchema>;
