import { AlertCircle, CheckCircle, X } from 'lucide-react'
import { useUIStore } from '../../store/uiStore'

export default function NotificationCenter() {
  const { errorMessage, successMessage, setErrorMessage, setSuccessMessage } = useUIStore()

  return (
    <div className="fixed bottom-4 right-4 space-y-2 pointer-events-none">
      {/* Error Notification */}
      {errorMessage && (
        <div className="animate-slideIn bg-red-50 border border-sap-error rounded-lg p-4 shadow-lg flex items-start gap-3 pointer-events-auto max-w-md">
          <AlertCircle className="w-5 h-5 text-sap-error flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-sap-error">Error</p>
            <p className="text-sm text-red-700 mt-1">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-500 hover:text-red-700"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Success Notification */}
      {successMessage && (
        <div className="animate-slideIn bg-green-50 border border-sap-success rounded-lg p-4 shadow-lg flex items-start gap-3 pointer-events-auto max-w-md">
          <CheckCircle className="w-5 h-5 text-sap-success flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-sap-success">Success</p>
            <p className="text-sm text-green-700 mt-1">{successMessage}</p>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-green-500 hover:text-green-700"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
