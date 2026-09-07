import { Check } from 'lucide-react'

interface Step {
  id: string
  label: string
  description: string
}

interface ProgressStepperProps {
  steps: Step[]
  currentStepIndex: number
}

export default function ProgressStepper({ steps, currentStepIndex }: ProgressStepperProps) {
  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center flex-1">
          {/* Step Circle */}
          <div className="flex flex-col items-center flex-shrink-0">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-all ${
                index < currentStepIndex
                  ? 'bg-sap-success text-white'
                  : index === currentStepIndex
                    ? 'bg-sap-blue text-white ring-2 ring-offset-2 ring-sap-blue'
                    : 'bg-gray-200 text-gray-600'
              }`}
            >
              {index < currentStepIndex ? (
                <Check className="w-5 h-5" />
              ) : (
                <span>{index + 1}</span>
              )}
            </div>
            <div className="text-center mt-2">
              <p
                className={`text-xs font-medium ${
                  index <= currentStepIndex ? 'text-sap-blue' : 'text-gray-500'
                }`}
              >
                {step.label}
              </p>
              <p className="text-xs text-gray-500">{step.description}</p>
            </div>
          </div>

          {/* Connector Line */}
          {index < steps.length - 1 && (
            <div className="flex-1 h-1 mx-2 bg-gray-300 relative">
              <div
                className={`absolute inset-y-0 left-0 h-full transition-all ${
                  index < currentStepIndex ? 'bg-sap-success' : 'bg-transparent'
                }`}
                style={{
                  width: index < currentStepIndex ? '100%' : '0%',
                }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
