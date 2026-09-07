import { ChevronRight, Download } from 'lucide-react'
import { useMappingStore } from '../../store/mappingStore'
import { useUIStore } from '../../store/uiStore'
import type { ReviewOrder, ReviewHeaderRow, ReviewLineItemRow } from '../../types'

export default function IntelligenceReview() {
  const { currentPurchaseOrder } = useMappingStore()
  const { setCurrentStep } = useUIStore()

  if (!currentPurchaseOrder) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-gray-600 mb-4">No PO data available. Please upload a PDF first.</p>
          <button
            onClick={() => setCurrentStep('ingestion')}
            className="px-6 py-2 bg-sap-blue text-white rounded-lg hover:bg-blue-800"
          >
            Go to Upload
          </button>
        </div>
      </div>
    )
  }

  const extractedData = currentPurchaseOrder.extractedJSON
  const orders: ReviewOrder[] = extractedData.orders || []

  return (
    <div className="h-full min-h-0 flex overflow-hidden">
      {/* Left Pane - PDF Viewer */}
      <div className="w-3/5 min-w-0 border-r border-gray-200 bg-gray-50 flex flex-col">
        <div className="bg-white border-b border-gray-200 px-4 py-3">
          <h3 className="font-semibold text-gray-900">{currentPurchaseOrder.fileName}</h3>
          <p className="text-xs text-gray-500 mt-1">
            Uploaded: {currentPurchaseOrder.uploadedAt.toLocaleString()}
          </p>
        </div>

        <div className="flex-1 min-h-0">
          {currentPurchaseOrder.fileUrl ? (
            <iframe
              src={currentPurchaseOrder.fileUrl}
              title="PDF Preview"
              className="h-full w-full"
            />
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-gray-500">
              PDF preview unavailable for this file.
            </div>
          )}
        </div>
      </div>

      {/* Right Pane - Extracted Data */}
      <div className="w-2/5 min-w-0 flex flex-col bg-white overflow-y-auto">
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">Extracted Data</h3>
            <button
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="Download"
            >
              <Download className="w-4 h-4 text-gray-600" />
            </button>
          </div>

          <p className="text-sm text-gray-600">
            {orders.length > 0 ? `Detected ${orders.length} purchase order(s)` : 'Detected purchase order data'}
          </p>
        </div>

        {/* Data Content */}
        <div className="px-6 py-4">
          <div className="space-y-6">
            {(orders.length > 0 ? orders : [{
              poIndex: 1,
              poNumber: extractedData.poNumber || 'PO-1',
              header: [],
              lineItems: extractedData.lineItems?.map((line) => ({
                lineNumber: line.lineNumber,
                poDescription: line.materialDescription,
                matnr: line.materialNumber || '',
                matchScore: 0,
                quantity: line.quantity,
                unit: line.unitOfMeasure,
                unitPrice: line.unitPrice || 0,
                totalPrice: line.totalPrice || 0,
                deliveryDate: extractedData.deliveryDate || '',
                status: line.materialNumber ? 'MATCHED' : 'UNMATCHED',
              })) || [],
            }] as ReviewOrder[]).map((order: ReviewOrder) => (
              <div key={order.poIndex} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <h4 className="text-sm font-semibold text-sap-blue mb-2">
                  PO {order.poIndex}: {order.poNumber}
                </h4>

                <div className="overflow-x-auto rounded border border-gray-200 bg-white mb-3">
                  <table className="w-full text-xs">
                    <thead className="bg-sap-blue text-white">
                      <tr>
                        <th className="px-2 py-1 text-left">SAP Field</th>
                        <th className="px-2 py-1 text-left">SAP Table</th>
                        <th className="px-2 py-1 text-left">Description</th>
                        <th className="px-2 py-1 text-left">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {order.header.map((row: ReviewHeaderRow, idx: number) => (
                        <tr key={idx} className="border-t border-gray-200">
                          <td className="px-2 py-1">{row.field}</td>
                          <td className="px-2 py-1">{row.table}</td>
                          <td className="px-2 py-1">{row.description}</td>
                          <td className="px-2 py-1">{row.value || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="overflow-x-auto rounded border border-gray-200 bg-white">
                  <table className="w-full text-xs">
                    <thead className="bg-sap-blue text-white">
                      <tr>
                        <th className="px-2 py-1 text-left">Line #</th>
                        <th className="px-2 py-1 text-left">PO Desc (JA)</th>
                        <th className="px-2 py-1 text-left">MATNR</th>
                        <th className="px-2 py-1 text-left">Match Score</th>
                        <th className="px-2 py-1 text-left">Qty</th>
                        <th className="px-2 py-1 text-left">Unit</th>
                        <th className="px-2 py-1 text-left">Unit Price</th>
                        <th className="px-2 py-1 text-left">Total Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {order.lineItems.map((line: ReviewLineItemRow, idx: number) => (
                        <tr key={idx} className="border-t border-gray-200">
                          <td className="px-2 py-1">{line.lineNumber}</td>
                          <td className="px-2 py-1">{line.poDescription}</td>
                          <td className="px-2 py-1">{line.matnr || '-'}</td>
                          <td className="px-2 py-1">{line.matchScore}%</td>
                          <td className="px-2 py-1">{line.quantity}</td>
                          <td className="px-2 py-1">{line.unit}</td>
                          <td className="px-2 py-1">{line.unitPrice ?? 0}</td>
                          <td className="px-2 py-1">{line.totalPrice ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="border-t border-gray-200 px-6 py-4 flex gap-3">
          <button
            onClick={() => setCurrentStep('ingestion')}
            className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium"
          >
            Back
          </button>
          <button
            onClick={() => setCurrentStep('mapping')}
            className="flex-1 px-4 py-2 bg-sap-blue text-white rounded-lg hover:bg-blue-800 transition-colors font-medium flex items-center justify-center gap-2"
          >
            Continue to Mapping
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
