import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/apiClient';
import { useUIStore } from '../store/uiStore';

/**
 * React hooks for API operations using TanStack Query
 * Handles data fetching, caching, and synchronization
 */

/**
 * Hook for uploading PDF and extracting data
 */
export const useUploadPDF = () => {
  const { setProcessing, updateProgress, setErrorMessage, setSuccessMessage } = useUIStore();

  return useMutation({
    mutationFn: async (file: File) => {
      try {
        setProcessing(true, 0);
        updateProgress(30);

        const response = await apiClient.uploadPDF(file);

        if (!response.success) {
          throw new Error(response.error?.message || 'Failed to upload PDF');
        }

        updateProgress(100);
        setSuccessMessage('PDF uploaded successfully. Processing OCR...');

        return response.data;
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'An error occurred';
        setErrorMessage(errorMsg);
        throw error;
      } finally {
        setProcessing(false);
      }
    },
    onSuccess: () => {
      setTimeout(() => setSuccessMessage(null), 3000);
    },
    onError: () => {
      setTimeout(() => setErrorMessage(null), 5000);
    },
  });
};

/**
 * Hook for fetching extracted data from uploaded PDF
 */
export const useGetExtractedData = (extractionId: string | null) => {
  return useQuery({
    queryKey: ['extractedData', extractionId],
    queryFn: async () => {
      if (!extractionId) throw new Error('No extraction ID provided');

      const response = await apiClient.getExtractedData(extractionId);

      if (!response.success) {
        throw new Error(response.error?.message || 'Failed to fetch extracted data');
      }

      return response.data;
    },
    enabled: !!extractionId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Hook for fetching mapping suggestions
 */
export const useGetMappingData = (extractionId: string | null) => {
  const { setErrorMessage } = useUIStore();

  return useQuery({
    queryKey: ['mappingData', extractionId],
    queryFn: async () => {
      if (!extractionId) throw new Error('No extraction ID provided');

      const response = await apiClient.getMappingData(extractionId);

      if (!response.success) {
        const errorMsg = response.error?.message || 'Failed to fetch mapping data';
        setErrorMessage(errorMsg);
        throw new Error(errorMsg);
      }

      return response.data;
    },
    enabled: !!extractionId,
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
};

/**
 * Hook for validating mapping data
 */
export const useValidateMapping = () => {
  return useMutation({
    mutationFn: async (mappingData: unknown) => {
      const response = await apiClient.validateMapping(mappingData);

      if (!response.success) {
        throw new Error(response.error?.message || 'Validation failed');
      }

      return response.data;
    },
  });
};

/**
 * Hook for pushing SAP sales order
 */
export const usePushToSAP = () => {
  const { setProcessing, updateProgress, setErrorMessage, setSuccessMessage } = useUIStore();

  return useMutation({
    mutationFn: async (salesOrderData: unknown) => {
      try {
        setProcessing(true, 0);
        updateProgress(50);

        const response = await apiClient.pushToSAP(salesOrderData);

        if (!response.success) {
          throw new Error(response.error?.message || 'Failed to push to SAP');
        }

        updateProgress(100);
        setSuccessMessage(`SAP order created successfully: ${response.data?.sapOrderNumber}`);

        return response.data;
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'An error occurred';
        setErrorMessage(errorMsg);
        throw error;
      } finally {
        setProcessing(false);
      }
    },
    onSuccess: () => {
      setTimeout(() => setSuccessMessage(null), 4000);
    },
    onError: () => {
      setTimeout(() => setErrorMessage(null), 5000);
    },
  });
};

/**
 * Hook for fetching master data (materials, customers, vendors)
 */
export const useMasterData = (type: 'materials' | 'customers' | 'vendors') => {
  return useQuery({
    queryKey: ['masterData', type],
    queryFn: async () => {
      const response = await apiClient.getMasterData(type);

      if (!response.success) {
        throw new Error(response.error?.message || `Failed to fetch ${type} data`);
      }

      return response.data?.data || [];
    },
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
};

/**
 * Hook for refetching data with manual triggers
 */
export const usePrefetchData = () => {
  return {
    prefetchExtractedData: async (extractionId: string) => {
      const response = await apiClient.getExtractedData(extractionId);
      return response;
    },
    prefetchMappingData: async (extractionId: string) => {
      const response = await apiClient.getMappingData(extractionId);
      return response;
    },
  };
};
