import { useEffect } from 'react'
import type { FC } from 'react'
import { useUIStore } from './store/uiStore'
import { useNotificaton } from './hooks/useNotification'
import IngestionHub from './components/IngestionHub/IngestionHub'
import IntelligenceReview from './components/IntelligenceReview/IntelligenceReview'
import SAPMapping from './components/SAPMapping/SAPMapping'
import Navigation from './components/Common/Navigation'
import ProgressStepper from './components/Common/ProgressStepper'
import NotificationCenter from './components/Common/NotificationCenter'
import './App.css'

const App: FC = () => {
  const { currentStep, setCurrentStep, sidebarExpanded, setSidebarExpanded } = useUIStore()

  useNotificaton()

  useEffect(() => {
    document.documentElement.classList.remove('dark')
  }, [])

  const steps = [
    { id: 'ingestion', label: 'Ingestion Hub', description: 'Upload PDF' },
    { id: 'review', label: 'Intelligence Review', description: 'Verify Data' },
    { id: 'mapping', label: 'SAP Mapping', description: 'Map Fields' },
    { id: 'confirmation', label: 'Confirmation', description: 'Submit' },
  ]

  const stepIndex = steps.findIndex((s) => s.id === currentStep)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-sap-bg">
      {/* Sidebar Navigation */}
      <Navigation
        steps={steps}
        currentStep={currentStep}
        onStepChange={(step) => setCurrentStep(step as 'ingestion' | 'review' | 'mapping' | 'confirmation')}
        isExpanded={sidebarExpanded}
        onToggleExpand={setSidebarExpanded}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex min-w-0 flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">SD-Automation</h1>
              <p className="text-sm text-gray-600 mt-1">Purchase Order to SAP Sales Order Transformation</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500">Step {stepIndex + 1} of {steps.length}</p>
            </div>
          </div>

          {/* Progress Stepper */}
          <ProgressStepper steps={steps} currentStepIndex={stepIndex} />
        </header>

        {/* Main Content */}
        <main className="flex-1 min-h-0 overflow-hidden">
          {currentStep === 'ingestion' && <IngestionHub />}
          {currentStep === 'review' && <IntelligenceReview />}
          {currentStep === 'mapping' && <SAPMapping />}
          {currentStep === 'confirmation' && (
            <div className="p-8 text-center">
              <h2 className="text-2xl font-bold text-sap-blue">Confirmation</h2>
              <p className="text-gray-600 mt-4">Review and submit your SAP sales order.</p>
            </div>
          )}
        </main>

        {/* Notification Center */}
        <NotificationCenter />
      </div>
    </div>
  )
}

export default App
