# SD-Automation: Purchase Order to SAP Sales Order Transformation

A high-performance React 19 + TypeScript application for extracting data from PDF Purchase Orders and transforming them into validated SAP Sales Order data.

## 🎯 Project Overview

SD-Automation automates the labor-intensive process of manually entering Purchase Order data into SAP. The system:

1. **Extracts** PO data via OCR (Python backend)
2. **Validates** extracted information using Zod schemas
3. **Maps** PO fields to SAP Sales Order format via an Excel-like editor
4. **Submits** validated data to SAP backend

## 🛠️ Tech Stack

### Frontend (This Project)
- **React 19** - UI library with StrictMode
- **TypeScript** - Strict mode type checking
- **Vite** - Lightning-fast build tool
- **Tailwind CSS** - Utility-first styling
- **Zustand** - lightweight state management for UI & mapping state
- **TanStack Query (React Query)** - Data fetching & caching
- **TanStack Table (React Table v8)** - Editable data grid for SAP mapping
- **React Hook Form** - Form state management
- **Zod** - TypeScript-first schema validation
- **react-dropzone** - File upload handling
- **lucide-react** - Beautiful icons

### Design System
**SAP Fiori Modernized** - Professional enterprise theme

- **Primary Color**: `#0070d2` (SAP Blue)
- **Background**: `#f4f7f9` (Light Industrial Gray)
- **Surface**: `#ffffff` (White)
- **Status Colors**:
  - Success: `#2b7d2b`
  - Warning: `#e9730c`
  - Error: `#bb0000`
- **Typography**: Inter font with SAP 72 spacing

### Backend (Python FastAPI)
- Python 3.9+
- FastAPI for REST API
- OCR processing (Tesseract or similar)
- SAP integration layer

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── IngestionHub/          # Step 1: PDF Upload with OCR skeleton
│   │   ├── IntelligenceReview/    # Step 2: 60/40 split PDF + JSON view
│   │   ├── SAPMapping/            # Step 3: Editable grid with validation
│   │   └── Common/
│   │       ├── Navigation.tsx      # Sidebar step navigation
│   │       ├── ProgressStepper.tsx # Visual step indicator
│   │       └── NotificationCenter.tsx # Toast notifications
│   ├── hooks/
│   │   ├── useAPI.ts              # TanStack Query hooks for API
│   │   └── useNotification.ts      # Notification manager
│   ├── store/
│   │   ├── uiStore.ts             # UI state (step, sidebar, modals)
│   │   └── mappingStore.ts        # Mapping data & validation state
│   ├── services/
│   │   └── apiClient.ts           # API client for backend communication
│   ├── types/
│   │   └── index.ts               # TypeScript interfaces
│   ├── lib/
│   │   ├── validation.ts          # Zod schemas for data validation
│   │   └── utils.ts               # Utility functions
│   ├── styles/
│   │   └── globals.css            # Tailwind + custom component styles
│   ├── pages/                     # (Optional) for future routing
│   ├── App.tsx                    # Main app container
│   ├── main.tsx                   # React entry point
│   └── index.css                  # Base styles
├── .env                           # Environment variables template
├── .env.local                     # Local overrides (gitignored)
├── tailwind.config.js             # Tailwind configuration with SAP colors
├── postcss.config.js              # PostCSS configuration
├── tsconfig.app.json              # TypeScript strict mode config
├── vite.config.ts                 # Vite bundler configuration
├── package.json                   # Dependencies & scripts
└── README.md                      # This file
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ and npm 9+
- Python 3.9+ with FastAPI backend running (see Backend Setup)
- Git

### Installation

1. **Clone and navigate to frontend**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure API endpoint**
   ```bash
   # Edit .env.local (or .env for defaults)
   VITE_API_URL=http://localhost:8000/api/v1
   ```

4. **Start development server**
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
npm run preview  # Preview production build locally
```

## 🔌 Backend Integration Guide

### API Contract

The frontend communicates with a Python FastAPI backend using these endpoints:

#### 1. **POST /api/v1/extract**
Upload a PDF for OCR processing.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/extract \
  -F "file=@purchase_order.pdf"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "extractionId": "extract_abc123",
    "status": "processing"
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

#### 2. **GET /api/v1/extract/{extractionId}**
Retrieve extracted PO data.

**Request:**
```bash
curl http://localhost:8000/api/v1/extract/extract_abc123
```

**Response:**
```json
{
  "success": true,
  "data": {
    "poNumber": "PO2026001",
    "poDate": "2026-04-01",
    "vendor": {
      "name": "Acme Corp",
      "number": "1000"
    },
    "lineItems": [
      {
        "description": "Widget A",
        "quantity": 100,
        "unitOfMeasure": "PC",
        "unitPrice": 25.50
      }
    ],
    "totalAmount": 2550,
    "currency": "USD",
    "rawText": "...",
    "rawJSON": {}
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

#### 3. **GET /api/v1/mapping/suggest/{extractionId}**
Get mapping suggestions based on extracted data.

**Response:**
```json
{
  "success": true,
  "data": {
    "mappings": [
      {
        "lineNumber": "10",
        "materialNumber": "12345678",
        "quantity": 100,
        "unitOfMeasure": "PC",
        "suggestedParty": "1000"
      }
    ]
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

#### 4. **POST /api/v1/mapping/validate**
Validate mapping data before submission.

**Request:**
```json
{
  "mappings": [
    {
      "lineNumber": "10",
      "materialNumber": "12345678",
      "quantity": 100,
      "unitOfMeasure": "PC",
      "soldToParty": "1000",
      "shipToParty": "1001",
      "pricingDate": "2026-04-29"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "isValid": true,
    "errors": []
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

#### 5. **POST /api/v1/sap/create-order**
Submit validated sales order to SAP.

**Request:**
```json
{
  "poNumber": "PO2026001",
  "poDate": "2026-04-01",
  "vendorNumber": "1000",
  "lineItems": [
    {
      "lineNumber": "10",
      "materialNumber": "12345678",
      "quantity": 100,
      "unitOfMeasure": "PC",
      "unitPrice": 25.50,
      "soldToParty": "1000",
      "shipToParty": "1001",
      "pricingDate": "2026-04-29"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "sapOrderNumber": "5000123456",
    "status": "created"
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

#### 6. **GET /api/v1/master-data/{type}**
Fetch master data (materials, customers, vendors).

**Parameters:**
- `type`: `materials` | `customers` | `vendors`

**Response:**
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "materialNumber": "12345678",
        "description": "Widget A",
        "unitPrice": 25.50
      }
    ]
  },
  "timestamp": "2026-04-29T18:00:00Z"
}
```

### Setting Up the Backend

#### Option 1: Using Provided Python Backend

If you have the Python backend in the parent directory (`../`):

```bash
# Install Python dependencies
cd ../
pip install -r requirements.txt

# Run FastAPI server
python -m uvicorn main:app --reload --port 8000
```

#### Option 2: Create Minimal FastAPI Backend

Create `backend/main.py`:

```python
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime
import uuid

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock extraction storage
extraction_cache = {}

@app.post("/api/v1/extract")
async def upload_pdf(file: UploadFile = File(...)):
    extraction_id = f"extract_{uuid.uuid4().hex[:8]}"
    
    # Simulate OCR processing
    extraction_cache[extraction_id] = {
        "filename": file.filename,
        "status": "completed"
    }
    
    return {
        "success": True,
        "data": {
            "extractionId": extraction_id,
            "status": "processing"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/extract/{extraction_id}")
async def get_extracted_data(extraction_id: str):
    return {
        "success": True,
        "data": {
            "poNumber": "PO2026001",
            "poDate": "2026-04-01",
            "vendor": {"name": "Sample Vendor", "number": "1000"},
            "lineItems": [
                {
                    "description": "Sample Material",
                    "quantity": 100,
                    "unitOfMeasure": "PC",
                    "unitPrice": 25.50
                }
            ],
            "totalAmount": 2550,
            "currency": "USD",
            "rawText": "...",
            "rawJSON": {}
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/sap/create-order")
async def create_sap_order(payload: dict):
    sap_order_number = f"5000{uuid.uuid4().hex[:8].upper()}"
    
    return {
        "success": True,
        "data": {
            "sapOrderNumber": sap_order_number,
            "status": "created"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/master-data/{data_type}")
async def get_master_data(data_type: str):
    return {
        "success": True,
        "data": {
            "data": []
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run with:
```bash
pip install fastapi uvicorn python-multipart
python backend/main.py
```

## 🧪 Development Workflow

### Running Type Checking

```bash
npm run tsc -- --noEmit  # Type check only (no build)
```

### Debugging

- **Chrome DevTools**: Press `F12` in browser
- **VS Code Debugger**: Add breakpoints and run debug session
- **React DevTools**: Install browser extension for component inspection

## 📦 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Backend API endpoint |
| `VITE_ENV` | `development` | Environment mode |
| `VITE_ENABLE_PDF_VIEWER` | `true` | Enable PDF preview (requires additional setup) |
| `VITE_ENABLE_MASTER_DATA_CACHE` | `true` | Cache master data in memory |

## 🎨 Customization

### Modifying Colors

Edit `tailwind.config.js`:
```javascript
theme: {
  extend: {
    colors: {
      'sap-blue': '#0070d2',      // Primary color
      'sap-success': '#2b7d2b',   // Success state
      'sap-warning': '#e9730c',   // Warning state
      'sap-error': '#bb0000',     // Error state
    },
  },
}
```

### Adding New Components

1. Create component file in `src/components/`
2. Use existing patterns (hooks, store, types)
3. Export from component's `index.ts` if needed

Example:
```tsx
// src/components/Custom/MyComponent.tsx
import { useUIStore } from '../../store/uiStore'

export default function MyComponent() {
  const { currentStep } = useUIStore()
  
  return <div>Component code</div>
}
```

## 🚨 Validation Rules

### Material Number (SAP)
- **Length**: 8-18 digits
- **Type**: Numeric only
- **Required**: Yes

### Quantity
- **Type**: Decimal (max 2 places)
- **Range**: > 0
- **Required**: Yes

### Unit of Measure
- **Allowed**: PC, KG, L, M, BOX, PALLET
- **Type**: Dropdown selection
- **Required**: Yes

### Party Number (KUNNR)
- **Length**: 1-10 digits
- **Type**: Numeric only
- **Required**: Yes for Sold-to and Ship-to

### Pricing Date
- **Format**: YYYY-MM-DD
- **Type**: ISO 8601 date
- **Required**: Yes

See `src/lib/validation.ts` for Zod schemas.

## 📋 Features Implemented

### Step 1: Ingestion Hub ✅
- Multi-file PDF dropzone with drag-and-drop
- File validation (MIME type, size)
- OCR processing progress indicator
- Error handling and retry logic
- Previous files history

### Step 2: Intelligence Review ✅
- 60/40 split pane layout
- PDF viewer placeholder (integrable with react-pdf)
- JSON/Table view toggle
- Syntax highlighting (via pre-formatted code)
- Download extracted data button
- Navigation to next step

### Step 3: SAP Mapping ✅
- TanStack Table v8 for editable grid
- Real-time cell validation
- Status indicators (Valid/Warning/Error)
- Dropdown selectors (UoM)
- Date picker
- Batch error checking before submission
- Submit to SAP functionality

### Navigation ✅
- Collapsible sidebar
- Step indicator with completed checkmarks
- Progress bar across steps
- Keyboard accessible

### Error Handling ✅
- Toast notifications (success/error)
- Field-level validation errors
- Row-level highlighting
- API error handling

## 🔒 Security Considerations

1. **CORS**: Backend must allow frontend origin
2. **CSRF Protection**: Implement if backend uses sessions
3. **Input Validation**: All inputs validated via Zod on frontend AND backend
4. **File Upload**: Only PDFs accepted, size-limited to 10MB
5. **API Keys**: Store sensitive data in environment variables (never in code)

## 📚 Additional Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [TanStack Query](https://tanstack.com/query/latest)
- [TanStack Table](https://tanstack.com/table/v8/docs/guide/introduction)
- [Zod Validation](https://zod.dev)
- [FastAPI](https://fastapi.tiangolo.com)

## 📝 License

This project is proprietary and confidential. All rights reserved.

## 👥 Support

For issues or questions, contact the development team or create an issue in the project repository.

---

**Last Updated**: April 29, 2026
**Version**: 1.0.0


The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
