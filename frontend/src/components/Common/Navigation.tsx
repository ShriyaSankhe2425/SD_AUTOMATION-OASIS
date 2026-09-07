import { ChevronLeft, FileText, CheckCircle2, Grid3x3, Flag } from 'lucide-react'

type StepId = 'ingestion' | 'review' | 'mapping' | 'confirmation'

interface Step {
  id: string
  label: string
  description: string
}

interface NavigationProps {
  steps: Step[]
  currentStep: StepId
  onStepChange: (step: StepId) => void
  isExpanded: boolean
  onToggleExpand: (expanded: boolean) => void
}

const stepIcons: Record<string, React.ReactNode> = {
  ingestion: <FileText className="w-5 h-5" />,
  review: <CheckCircle2 className="w-5 h-5" />,
  mapping: <Grid3x3 className="w-5 h-5" />,
  confirmation: <Flag className="w-5 h-5" />,
}

export default function Navigation({
  steps,
  currentStep,
  onStepChange,
  isExpanded,
  onToggleExpand,
}: NavigationProps) {
  return (
    <nav
      className={`bg-white border-r border-gray-200 transition-all duration-300 flex flex-col ${
        isExpanded ? 'w-64' : 'w-24'
      }`}
    >
      {/* Header */}
      <div className="px-4 py-6 border-b border-gray-200">
        <div className="flex items-center justify-between gap-2">
          <div className={`${isExpanded ? '' : 'hidden'}`}>
            <h2 className="text-lg font-bold text-sap-blue">SD Auto</h2>
            <p className="text-xs text-gray-500">PO to Sales Order</p>
          </div>
          <button
            onClick={() => onToggleExpand(!isExpanded)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            <ChevronLeft className={`w-4 h-4 transition-transform ${isExpanded ? '' : 'rotate-180'}`} />
          </button>
        </div>
      </div>

      {/* Steps Navigation */}
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-2">
        {steps.map((step) => {
          const isActive = currentStep === step.id
          return (
            <button
              key={step.id}
              onClick={() => onStepChange(step.id as StepId)}
              className={`w-full px-4 py-3 rounded-lg flex items-center gap-3 transition-all ${
                isActive
                  ? 'bg-sap-blue text-white shadow-md'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <div className="flex-shrink-0">{stepIcons[step.id]}</div>
              {isExpanded && (
                <div className="text-left flex-1">
                  <p className="text-sm font-medium">{step.label}</p>
                  <p className={`text-xs ${isActive ? 'text-blue-100' : 'text-gray-500'}`}>
                    {step.description}
                  </p>
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Footer */}
      <div className={`border-t border-gray-200 px-4 py-4 text-center text-xs text-gray-500 ${isExpanded ? '' : 'hidden'}`}>
        <p>v1.0.0</p>
        <p className="mt-1">© 2026 SD Automation</p>
      </div>
    </nav>
  )
}
