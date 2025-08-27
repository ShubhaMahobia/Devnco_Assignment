# RAG Frontend Application

A modern React-based frontend for the RAG (Retrieval-Augmented Generation) system that provides document upload, management, and PDF viewing capabilities.

## Features

### ✅ Implemented Features
- **Document Upload**: Drag & drop or click to upload PDF, DOCX, and TXT files
- **File Management**: List, select, and delete uploaded documents
- **PDF Viewer**: Interactive PDF viewer with page navigation controls
- **Real-time Updates**: Automatic file list refresh after upload/delete operations
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Backend Health Check**: Connection status monitoring with retry functionality
- **Responsive Design**: Mobile-friendly layout that adapts to different screen sizes

### 🎨 User Interface
- **Left Sidebar**: File library with upload functionality and file list
- **Main Content**: PDF viewer with navigation controls and document information
- **Modern Styling**: Clean, professional design with intuitive user experience

## Quick Start

### Prerequisites
- Node.js 14+ and npm
- Backend server running on `http://127.0.0.1:8000`

### Installation & Running

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Start the development server**
   ```bash
   npm start
   ```

3. **Open in browser**
   - Application: http://localhost:3000
   - Ensure backend is running for full functionality

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── FileList.js          # File upload and management component
│   │   └── PDFViewer.js         # PDF viewing and navigation component
│   ├── services/
│   │   └── api.js               # Backend API communication layer
│   ├── App.js                   # Main application component
│   ├── App.css                  # Application styles
│   └── index.js                 # Application entry point
├── public/
│   └── index.html               # HTML template
└── package.json                 # Dependencies and scripts
```

## API Integration

The frontend communicates with the FastAPI backend through these endpoints:

### File Management
- `POST /api/v1/files/upload` - Upload new files
- `GET /api/v1/files/list` - List all uploaded files
- `GET /api/v1/files/{file_id}/download` - Download/view files
- `DELETE /api/v1/files/delete/{file_id}` - Delete files
- `GET /api/v1/files/{file_id}/info` - Get file information

### Health Check
- `GET /api/v1/health/` - Backend health status

## Component Details

### FileList Component
- **File Upload**: Supports drag & drop and click-to-browse
- **File Validation**: Checks file type (.pdf, .docx, .txt) and size (max 50MB)
- **File List**: Displays uploaded files with metadata (size, upload date)
- **File Actions**: Select files for viewing, delete unwanted files
- **Real-time Feedback**: Success/error messages for all operations

### PDFViewer Component
- **PDF Rendering**: Uses react-pdf for high-quality PDF display
- **Page Navigation**: Previous/Next buttons and direct page input
- **Document Info**: Shows filename, file type, and file size
- **Error Handling**: Graceful handling of PDF loading errors
- **Empty States**: User-friendly messages when no file is selected

### API Service Layer
- **Axios Integration**: Centralized HTTP client configuration
- **Error Handling**: Consistent error handling across all API calls
- **Response Processing**: Automatic data extraction and formatting
- **Base URL Configuration**: Easy backend URL management

## File Support

### Supported File Types
- **PDF** (.pdf) - Full viewing support with page navigation
- **Word Documents** (.docx) - Upload and storage (preview coming soon)
- **Text Files** (.txt) - Upload and storage (preview coming soon)

### File Size Limits
- Maximum file size: 50MB
- Validation performed on both frontend and backend
- Clear error messages for oversized files

## Styling & Design

### Design System
- **Color Palette**: Professional blue and gray tones
- **Typography**: System fonts for optimal readability
- **Layout**: Flexbox-based responsive design
- **Components**: Consistent button styles and form elements

### Responsive Behavior
- **Desktop**: Side-by-side layout (sidebar + main content)
- **Mobile**: Stacked layout with collapsible sidebar
- **Tablet**: Adaptive layout based on screen width

## Development

### Available Scripts
- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run test suite
- `npm eject` - Eject from Create React App (irreversible)

### Dependencies
- **React 19.1.1** - Core framework
- **axios** - HTTP client for API communication
- **react-pdf** - PDF viewing and rendering

### Development Notes
- Built with Create React App for easy setup and development
- Uses functional components with React Hooks
- Implements modern JavaScript (ES6+) features
- Follows React best practices and conventions

## Configuration

### Backend URL
Update the API base URL in `src/services/api.js`:
```javascript
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
```

### CORS
Ensure the backend allows frontend origin in CORS configuration.

## Troubleshooting

### Common Issues

1. **Backend Connection Error**
   - Ensure backend server is running on port 8000
   - Check CORS configuration in backend
   - Verify API endpoints are accessible

2. **PDF Loading Issues**
   - Ensure PDF files are valid and not corrupted
   - Check browser console for PDF.js errors
   - Verify download endpoint is working

3. **File Upload Failures**
   - Check file size (must be under 50MB)
   - Verify file type is supported
   - Ensure sufficient storage space on backend

### Browser Compatibility
- Chrome 80+ (recommended)
- Firefox 75+
- Safari 13+
- Edge 80+

## Future Enhancements

### Planned Features
- **Q&A Interface**: Chat interface for document questions
- **Document Preview**: Text and DOCX file previews
- **Search Functionality**: Search through uploaded documents
- **Batch Operations**: Multiple file upload and management
- **User Authentication**: User accounts and file privacy
- **Document Annotations**: PDF annotation and highlighting tools

## Contributing

When contributing to the frontend:

1. Follow React best practices and conventions
2. Maintain consistent code formatting
3. Add appropriate error handling
4. Update documentation for new features
5. Test across different browsers and devices
6. Ensure responsive design principles are followed

## License

This project is part of the RAG Application system. See the main project README for license information.