import { useEffect } from 'react'
import { useUIStore } from '../store/uiStore'

export const useNotificaton = () => {
  const { errorMessage, successMessage, setErrorMessage, setSuccessMessage } = useUIStore()

  useEffect(() => {
    if (errorMessage) {
      const timer = setTimeout(() => setErrorMessage(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [errorMessage, setErrorMessage])

  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [successMessage, setSuccessMessage])
}
