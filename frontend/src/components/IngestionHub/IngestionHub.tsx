import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, AlertCircle, Loader } from 'lucide-react'
import { useMappingStore } from '../../store/mappingStore'
import { useUIStore } from '../../store/uiStore'
import { useUploadPDF } from '../../hooks/useAPI'
import { apiClient } from '../../services/apiClient'
import { isSupportedUploadFile, formatFileSize } from '../../lib/utils'
import type { SalesOrderMapping } from '../../types'

export default function IngestionHub() {
  const { setCurrentStep, setSuccessMessage } = useUIStore()
  const { setCurrentPurchaseOrder, setMappingRows } = useMappingStore()
  const { mutateAsync: uploadPDF, isPending } = useUploadPDF()
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const [errors, setErrors] = useState<string[]>([])
  const [processingSeconds, setProcessingSeconds] = useState(0)
  const [lastProcessingSeconds, setLastProcessingSeconds] = useState<number | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setErrors([])
    const validFiles: File[] = []
    const newErrors: string[] = []

    acceptedFiles.forEach((file) => {
      if (isSupportedUploadFile(file)) {
        validFiles.push(file)
      } else {
        newErrors.push(`${file.name}: Invalid file type. Please upload PDF or image files only.`)
      }

      if (file.size > 10 * 1024 * 1024) {
        newErrors.push(`${file.name}: File size exceeds 10MB limit.`)
      }
    })

    if (newErrors.length > 0) {
      setErrors(newErrors)
    }

    if (validFiles.length > 0) {
      setUploadedFiles((prev) => [...prev, ...validFiles])
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.webp'],
    },
  })

  const handleProcessFile = async (file: File) => {
    const startedAt = Date.now()
    setProcessingSeconds(0)
    const timer = window.setInterval(() => {
      setProcessingSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    try {
      const upload = await uploadPDF(file)
      const extractionId = upload?.extractionId
      if (!extractionId) {
        throw new Error('Missing extractionId from upload response')
      }

      const extractedRes = await apiClient.getExtractedData(extractionId)
      if (!extractedRes.success || !extractedRes.data) {
        throw new Error(extractedRes.error?.message || 'Failed to load extracted data')
      }

      const mappingRes = await apiClient.getMappingData(extractionId)
      if (!mappingRes.success) {
        throw new Error(mappingRes.error?.message || 'Failed to load mapping data')
      }

      const extracted = extractedRes.data
      const mappingRows: SalesOrderMapping[] = (mappingRes.data?.mappings || []).map((row, idx) => ({
        poNumber: row.poNumber || extracted.poNumber || `PO-${idx + 1}`,
        lineNumber: row.lineNumber || `${(idx + 1) * 10}`,
        materialNumber: row.materialNumber || '',
        materialDescription: row.materialDescription || extracted.lineItems?.[idx]?.materialDescription || '',
        quantity: row.quantity || 0,
        unitOfMeasure: row.unitOfMeasure || 'PC',
        unitPrice: row.unitPrice || extracted.lineItems?.[idx]?.unitPrice || 0,
        totalPrice: row.totalPrice || extracted.lineItems?.[idx]?.totalPrice || 0,
        soldToParty: { value: row.suggestedSoldTo || '', label: row.suggestedSoldTo || '' },
        shipToParty: { value: row.suggestedShipTo || '', label: row.suggestedShipTo || '' },
        pricingDate: new Date(row.pricingDate || extracted.poDate),
        validationStatus: {
          isValid: !!row.materialNumber && !!row.suggestedSoldTo && !!row.suggestedShipTo,
          severity: !!row.materialNumber && !!row.suggestedSoldTo && !!row.suggestedShipTo ? 'info' : 'warning',
          message: !row.materialNumber ? 'Material number needs verification' : undefined,
        },
        validationErrors: !row.materialNumber
          ? [{ field: 'materialNumber', message: 'Material Number is required', severity: 'warning' }]
          : [],
      }))

      const po = {
        id: extractionId,
        fileName: file.name,
        fileUrl: URL.createObjectURL(file),
        uploadedAt: new Date(),
        extractedText: 'PO extracted via OCR',
        extractedJSON: extracted,
        status: 'completed' as const,
      }

      const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000)
      setSuccessMessage(`Processing completed in ${elapsedSeconds}s`)
      setCurrentPurchaseOrder(po)
      setMappingRows(mappingRows)
      setCurrentStep('review')
    } catch (error) {
      console.error('Processing failed:', error)
    } finally {
      window.clearInterval(timer)
      setLastProcessingSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }
  }

  const handleRemoveFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="h-full overflow-auto p-6 md:p-8 space-y-6">
      {/* Dropzone */}
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Purchase Order</h2>
          <p className="text-gray-600">Drag and drop your PDF or image files, or click to browse</p>
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${
            isDragActive
              ? 'border-sap-blue bg-blue-50'
              : 'border-gray-300 hover:border-sap-blue hover:bg-gray-50'
          } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <input {...getInputProps()} disabled={isPending} />
          <div className="space-y-3">
            <div className="flex justify-center">
              {isPending ? (
                <Loader className="w-12 h-12 text-sap-blue animate-spin" />
              ) : (
                <Upload className="w-12 h-12 text-sap-blue" />
              )}
            </div>
            <div>
              <p className="text-lg font-medium text-gray-900">
                {isDragActive ? 'Drop files here' : 'Drag files here or click to select'}
              </p>
              <p className="text-sm text-gray-500 mt-1">Supported formats: PDF, PNG, JPG, JPEG, WEBP (max 10MB)</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error Messages */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-sap-error rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-sap-error flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-medium text-sap-error mb-2">Upload Errors</h3>
              <ul className="space-y-1">
                {errors.map((error, idx) => (
                  <li key={idx} className="text-sm text-red-700">
                    {error}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">Uploaded Files</h3>
          <div className="space-y-2">
            {uploadedFiles.map((file, idx) => (
              <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1">
                  <File className="w-8 h-8 text-red-500" />
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{file.name}</p>
                    <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleProcessFile(file)}
                    disabled={isPending}
                    className="px-4 py-2 bg-sap-blue text-white rounded-lg hover:bg-blue-800 disabled:opacity-50 transition-colors font-medium"
                  >
                    {isPending ? `Processing... ${processingSeconds}s` : 'Process'}
                  </button>
                  <button
                    onClick={() => handleRemoveFile(idx)}
                    disabled={isPending}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
          {lastProcessingSeconds !== null && !isPending && (
            <p className="text-sm text-gray-600">
              Last processing time: <span className="font-semibold">{lastProcessingSeconds}s</span>
            </p>
          )}
        </div>
      )}

      {/* Info Card */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-2">
        <h4 className="font-medium text-gray-900">What happens next?</h4>
        <ul className="space-y-1 text-sm text-gray-700">
          <li>✓ Your PDF or image will be processed using OCR technology</li>
          <li>✓ Purchase order data will be automatically extracted</li>
          <li>✓ Data will be validated and prepared for SAP mapping</li>
        </ul>
      </div>
    </div>
  )
}
