import { create } from 'zustand';

type Step = 'ingestion' | 'review' | 'mapping' | 'confirmation';

interface PreviousFileData {
  filename: string;
  url: string;
}

interface UIState {
  // Navigation
  currentStep: Step;
  setCurrentStep: (step: Step) => void;

  // Sidebar
  sidebarExpanded: boolean;
  setSidebarExpanded: (expanded: boolean) => void;

  // File processing
  isProcessing: boolean;
  processingProgress: number;
  setProcessing: (processing: boolean, progress?: number) => void;
  updateProgress: (progress: number) => void;

  // Modal/Dialog state
  showConfirmDialog: boolean;
  setShowConfirmDialog: (show: boolean) => void;

  // Error handling
  errorMessage: string | null;
  setErrorMessage: (message: string | null) => void;

  // Success message
  successMessage: string | null;
  setSuccessMessage: (message: string | null) => void;

  // PDF view state
  currentPDFUrl: string | null;
  setCurrentPDFUrl: (url: string | null) => void;

  // Previous files for re-processing
  previousFiles: PreviousFileData[];
  addPreviousFile: (file: PreviousFileData) => void;
  removePreviousFile: (filename: string) => void;

  // Dark mode (optional feature)
  darkMode: boolean;
  setDarkMode: (dark: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  // Navigation
  currentStep: 'ingestion',
  setCurrentStep: (step: Step) => set({ currentStep: step }),

  // Sidebar
  sidebarExpanded: true,
  setSidebarExpanded: (expanded: boolean) => set({ sidebarExpanded: expanded }),

  // File processing
  isProcessing: false,
  processingProgress: 0,
  setProcessing: (processing: boolean, progress: number = 0) =>
    set({ isProcessing: processing, processingProgress: progress }),
  updateProgress: (progress: number) => set({ processingProgress: progress }),

  // Modal/Dialog
  showConfirmDialog: false,
  setShowConfirmDialog: (show: boolean) => set({ showConfirmDialog: show }),

  // Error handling
  errorMessage: null,
  setErrorMessage: (message: string | null) => set({ errorMessage: message }),

  // Success message
  successMessage: null,
  setSuccessMessage: (message: string | null) => set({ successMessage: message }),

  // PDF view state
  currentPDFUrl: null,
  setCurrentPDFUrl: (url: string | null) => set({ currentPDFUrl: url }),

  // Previous files
  previousFiles: [],
  addPreviousFile: (file: PreviousFileData) =>
    set((state) => ({
      previousFiles: [...state.previousFiles, file],
    })),
  removePreviousFile: (filename: string) =>
    set((state) => ({
      previousFiles: state.previousFiles.filter((f) => f.filename !== filename),
    })),

  // Dark mode
  darkMode: false,
  setDarkMode: (dark: boolean) => set({ darkMode: dark }),
}));
