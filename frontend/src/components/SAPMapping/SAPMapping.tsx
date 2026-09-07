import { useMemo, useState } from 'react'
import { Check, ChevronLeft, Copy, Send, X } from 'lucide-react'
import { useMappingStore } from '../../store/mappingStore'
import { useUIStore } from '../../store/uiStore'
import type { ReviewHeaderRow, ReviewOrder, SalesOrderMapping } from '../../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

/** First segment of a pipe-joined value (e.g. "D1|D1" -> "D1"), since SAP
 * fields take a single code, not the pipe-joined list of all matches. */
const firstOf = (value: string): string => (value || '').split('|')[0]?.trim() || ''

/** Distinct, trimmed segments of a pipe-joined value, e.g. "D1|D1|D2" -> ["D1", "D2"]. */
const splitOptions = (value: string): string[] =>
  Array.from(new Set((value || '').split('|').map((v) => v.trim()).filter(Boolean)))

const DROPDOWN_FIELDS = new Set(['VTWEG', 'SPART'])

/** Convert an extracted date string (often "2024年 7月 26日" / "21年06月23日" style, never
 * ISO) into the SAP OData V2 "/Date(epochMillis)/" wire format. */
function toSapDate(raw: string): string {
  const jpMatch = (raw || '').match(/(\d{2,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/)
  let year: number, month: number, day: number
  if (jpMatch) {
    year = parseInt(jpMatch[1], 10)
    if (year < 100) year += 2000
    month = parseInt(jpMatch[2], 10)
    day = parseInt(jpMatch[3], 10)
  } else {
    const parsed = new Date(raw)
    if (isNaN(parsed.getTime())) return '/Date(0)/'
    year = parsed.getUTCFullYear()
    month = parsed.getUTCMonth() + 1
    day = parsed.getUTCDate()
  }
  return `/Date(${Date.UTC(year, month - 1, day)})/`
}

export default function SAPMapping() {
  const { mappingRows, currentPurchaseOrder } = useMappingStore()
  const { setCurrentStep } = useUIStore()

  const [rows, setRows] = useState<SalesOrderMapping[]>(mappingRows)
  const [payloadPreview, setPayloadPreview] = useState<object | null>(null)
  const [copied, setCopied] = useState(false)
  const sourceOrders: ReviewOrder[] = currentPurchaseOrder?.extractedJSON.orders || []
  const [orderHeaders, setOrderHeaders] = useState<Record<string, ReviewHeaderRow[]>>(() => {
    const init: Record<string, ReviewHeaderRow[]> = {}
    sourceOrders.forEach((order) => {
      init[order.poNumber] = order.header.map((row) => {
        if (row.field === 'AUART') return { ...row, value: row.value || '' }
        // Multi-match fields (e.g. "D1|D1|D2") start pre-selected on the
        // first option; the full option list is re-derived from sourceOrders.
        if (DROPDOWN_FIELDS.has(row.field)) return { ...row, value: firstOf(row.value) }
        return row
      })
    })
    return init
  })

  const getFieldOptions = (poNumber: string, field: string): string[] => {
    const row = sourceOrders.find((o) => o.poNumber === poNumber)?.header.find((h) => h.field === field)
    return splitOptions(row?.value || '')
  }

  const grouped = useMemo(() => {
    const groups: Record<string, { row: SalesOrderMapping; idx: number }[]> = {}
    rows.forEach((row, idx) => {
      const key = row.poNumber || 'UNKNOWN_PO'
      if (!groups[key]) groups[key] = []
      groups[key].push({ row, idx })
    })
    return groups
  }, [rows])

  const updateRowByIndex = (idx: number, updates: Partial<SalesOrderMapping>) => {
    setRows((prev) => prev.map((row, i) => (i === idx ? { ...row, ...updates } : row)))
  }

  const updateHeaderValue = (poNumber: string, field: string, value: string) => {
    setOrderHeaders((prev) => ({
      ...prev,
      [poNumber]: (prev[poNumber] || []).map((row) => (row.field === field ? { ...row, value } : row)),
    }))
  }

  const isUserAttentionField = (field: string) =>
    field === 'AUART' || field === 'KUNNR (Sold-to)' || field === 'KUNNR (Ship-to)'

  const getHeaderValue = (poNumber: string, field: string): string =>
    (orderHeaders[poNumber] || []).find((h) => h.field === field)?.value?.trim() || ''

  const handleSubmit = () => {
    const missingAuart = Object.values(orderHeaders).some(
      (headers: ReviewHeaderRow[]) => !headers.find((h: ReviewHeaderRow) => h.field === 'AUART')?.value?.trim()
    )
    if (missingAuart) {
      alert('Sales Order Type (AUART) is required for each PO.')
      return
    }

    const salesOrders = Object.entries(grouped).map(
      ([poNumber, items]: [string, { row: SalesOrderMapping; idx: number }[]]) => {
        const customerDate = toSapDate(getHeaderValue(poNumber, 'BSTDK'))
        return {
          SalesOrderType: getHeaderValue(poNumber, 'AUART'),
          SalesOrganization: getHeaderValue(poNumber, 'VKORG'),
          DistributionChannel: firstOf(getHeaderValue(poNumber, 'VTWEG')),
          OrganizationDivision: firstOf(getHeaderValue(poNumber, 'SPART')),
          SoldToParty: getHeaderValue(poNumber, 'KUNNR (Sold-to)'),
          PurchaseOrderByCustomer: getHeaderValue(poNumber, 'BSTNK') || poNumber,
          CustomerPurchaseOrderDate: customerDate,
          PricingDate: customerDate,
          to_Partner: [
            { PartnerFunction: 'AG', Customer: getHeaderValue(poNumber, 'KUNNR (Sold-to)') },
            { PartnerFunction: 'WE', Customer: getHeaderValue(poNumber, 'KUNNR (Ship-to)') },
          ],
          to_Item: items.map(({ row }) => ({
            SalesOrderItem: row.lineNumber,
            Material: row.materialNumber,
            RequestedQuantity: String(row.quantity),
            RequestedQuantityUnit: row.unitOfMeasure,
          })),
        }
      }
    )

    // Most SAP OData sales-order-create services take one order per call;
    // send a single object when there's only one PO, otherwise an array.
    const sapPayload = salesOrders.length === 1 ? salesOrders[0] : salesOrders

    setCopied(false)
    setPayloadPreview(sapPayload)
  }

  const copyPayload = async () => {
    if (!payloadPreview) return
    await navigator.clipboard.writeText(JSON.stringify(payloadPreview, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="p-6 md:p-8 h-full overflow-y-auto flex flex-col">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">SAP Mapping Grid</h2>
        <p className="text-gray-600">Header + line-item mapping per PO for SAP submission.</p>
      </div>

      {rows.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 text-sm text-gray-600">
          No extracted mapping data available yet. Upload and process a PDF first.
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-sm text-blue-900">
        <span className="font-semibold">Note:</span> Sales Order Type, Sold-to Party, and Ship-to Party are highlighted in amber below for convenience &mdash; edit them if needed.
      </div>

      <div className="space-y-6 mb-6">
        {Object.entries(grouped).map(([poNumber, items]: [string, { row: SalesOrderMapping; idx: number }[]], groupIdx) => (
          <section key={poNumber} className="rounded-lg border border-gray-200 bg-white">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
              <h3 className="font-semibold text-sap-blue">PO {groupIdx + 1}: {poNumber}</h3>
            </div>

            <div className="p-4 overflow-x-auto">
              <h4 className="text-sm font-semibold text-gray-800 mb-2">Header Fields</h4>
              <table className="w-full text-xs border border-gray-200 mb-4">
                <thead className="bg-sap-blue text-white">
                  <tr>
                    <th className="px-2 py-1 text-left">SAP Field</th>
                    <th className="px-2 py-1 text-left">Description</th>
                    <th className="px-2 py-1 text-left">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {(orderHeaders[poNumber] || []).map((h: ReviewHeaderRow, idx: number) => {
                    const options = DROPDOWN_FIELDS.has(h.field) ? getFieldOptions(poNumber, h.field) : []
                    const inputClassName = `w-full px-2 py-1 border rounded text-xs ${
                      isUserAttentionField(h.field)
                        ? 'border-amber-400 bg-amber-50 text-amber-900'
                        : 'border-gray-300'
                    }`
                    return (
                    <tr key={idx} className="border-t border-gray-200">
                      <td className={`px-2 py-1 ${isUserAttentionField(h.field) ? 'bg-amber-100 font-semibold text-amber-900' : ''}`}>{h.field}</td>
                      <td className="px-2 py-1">{h.description}</td>
                      <td className="px-2 py-1">
                        {options.length > 1 ? (
                          <select
                            value={h.value || ''}
                            onChange={(e) => updateHeaderValue(poNumber, h.field, e.target.value)}
                            className={`${inputClassName} bg-white`}
                          >
                            {options.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={h.value || ''}
                            onChange={(e) => updateHeaderValue(poNumber, h.field, e.target.value)}
                            placeholder={h.field === 'AUART' ? 'Enter Sales Order Type (required)' : '-'}
                            className={inputClassName}
                          />
                        )}
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>

              <h4 className="text-sm font-semibold text-gray-800 mb-2">Line Items</h4>
              <table className="w-full text-xs border border-gray-200">
                <thead className="bg-sap-blue text-white">
                  <tr>
                    <th className="px-2 py-1 text-left">Line #</th>
                    <th className="px-2 py-1 text-left">Description</th>
                    <th className="px-2 py-1 text-left">MATNR</th>
                    <th className="px-2 py-1 text-left">Qty</th>
                    <th className="px-2 py-1 text-left">Unit</th>
                    <th className="px-2 py-1 text-left">Unit Price</th>
                    <th className="px-2 py-1 text-left">Total Price</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(({ row, idx }: { row: SalesOrderMapping; idx: number }) => (
                    <tr key={`${poNumber}-${idx}`} className="border-t border-gray-200">
                      <td className="px-2 py-1">{row.lineNumber}</td>
                      <td className="px-2 py-1">{row.materialDescription}</td>
                      <td className="px-2 py-1"><input className="w-full px-1 py-1 border border-gray-300 rounded" value={row.materialNumber} onChange={(e) => updateRowByIndex(idx, { materialNumber: e.target.value })} /></td>
                      <td className="px-2 py-1"><input type="number" className="w-full px-1 py-1 border border-gray-300 rounded" value={row.quantity} onChange={(e) => updateRowByIndex(idx, { quantity: parseFloat(e.target.value) || 0 })} /></td>
                      <td className="px-2 py-1"><input className="w-full px-1 py-1 border border-gray-300 rounded" value={row.unitOfMeasure} onChange={(e) => updateRowByIndex(idx, { unitOfMeasure: e.target.value })} /></td>
                      <td className="px-2 py-1"><input type="number" className="w-full px-1 py-1 border border-gray-300 rounded" value={row.unitPrice || 0} onChange={(e) => updateRowByIndex(idx, { unitPrice: parseFloat(e.target.value) || 0 })} /></td>
                      <td className="px-2 py-1"><input type="number" className="w-full px-1 py-1 border border-gray-300 rounded" value={row.totalPrice || 0} onChange={(e) => updateRowByIndex(idx, { totalPrice: parseFloat(e.target.value) || 0 })} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>

      <div className="flex gap-3 justify-end">
        <button
          onClick={() => setCurrentStep('review')}
          className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium flex items-center gap-2"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <button
          onClick={handleSubmit}
          className="px-6 py-2 bg-sap-blue text-white rounded-lg hover:bg-blue-800 transition-colors font-medium flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
          Push to SAP
        </button>
      </div>

      {payloadPreview && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <div>
                <h3 className="font-semibold text-gray-900">SAP Sales Order Payload</h3>
                <p className="text-xs text-gray-500 mt-1">
                  API not connected yet &mdash; copy this and test manually with Postman.
                </p>
              </div>
              <button
                onClick={() => setPayloadPreview(null)}
                className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-5 py-3 border-b border-gray-200 bg-gray-50 text-xs text-gray-700 space-y-1">
              <div><span className="font-semibold">Method:</span> POST</div>
              <div className="break-all"><span className="font-semibold">URL:</span> {API_BASE_URL}/sap/create-order</div>
              <div><span className="font-semibold">Headers:</span> Content-Type: application/json</div>
            </div>

            <pre className="flex-1 overflow-auto px-5 py-4 text-xs bg-gray-900 text-green-300 whitespace-pre-wrap break-all">
              {JSON.stringify(payloadPreview, null, 2)}
            </pre>

            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-200">
              <button
                onClick={() => setPayloadPreview(null)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium"
              >
                Close
              </button>
              <button
                onClick={copyPayload}
                className="px-4 py-2 bg-sap-blue text-white rounded-lg hover:bg-blue-800 transition-colors font-medium flex items-center gap-2"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied!' : 'Copy to Clipboard'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
