import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header'; // Importando o Header component
import './UploadResumePage.css';
import { analyzeResume } from "../services/authService"; 


const UploadResumePage = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const user = JSON.parse(localStorage.getItem('user'));
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB em bytes

  const handleLogout = async () => {
    const { handleLogout: logoutHelper } = await import('../utils/logoutHelper');
    await logoutHelper();
  };

  const validateFile = (file) => {
    if (file.type !== 'application/pdf') {
      setError('Por favor, envie apenas arquivos PDF.');
      return false;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('O arquivo excede o tamanho máximo de 10MB.');
      return false;
    }
    setError('');
    return true;
  };

  const handleFileSelect = (file) => {
    if (validateFile(file)) {
      setSelectedFile(file);
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedFile) {
      setError("Por favor, selecione um arquivo PDF.");
      return;
    }

    setIsUploading(true);
    setError("");

    try {
      const result = await analyzeResume(selectedFile);

      console.log("Resultado da análise do currículo:", result);
      // Redireciona para a página de resultado com o ID
      navigate(`/analise-curriculo/${result.id}`);

    } catch (err) {
      console.error('Erro completo:', err);
      
      // Mensagem de erro mais específica
      let errorMessage = 'Erro ao fazer upload do currículo. Tente novamente.';
      
      if (err.message) {
        // Tenta extrair a mensagem de erro do backend
        if (err.status === 429) {
          errorMessage = 'Limite de uso da API do Gemini excedido. Por favor, aguarde alguns minutos e tente novamente.';
        } else if (err.message.includes('API key') || err.message.includes('autenticação') || err.message.includes('expired')) {
          errorMessage = 'Erro de autenticação com a API. A chave de API pode ter expirado. Entre em contato com o suporte.';
        } else if (err.message.includes('PDF') || err.message.includes('arquivo')) {
          errorMessage = err.message;
        } else if (err.message.length > 0 && err.message.length < 200) {
          errorMessage = err.message;
        }
      }
      
      setError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-container">
      {/* Header component */}
      <Header user={user} onLogout={handleLogout} />

      {/* Main Content */}
      <main className="upload-main">
        <div className="upload-card">
          <div className="upload-header-section">
            <h1 className="upload-title">Análise Inteligente de Currículo</h1>
            <p className="upload-description">
              Envie seu currículo em PDF e nossa IA criará uma análise detalhada com sugestões de melhoria
            </p>
          </div>

          <form onSubmit={handleSubmit} className="upload-form">
            {error && <p className="error">{error}</p>}

            <div
              className={`upload-area ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={handleUploadClick}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileInputChange}
                className="file-input"
                style={{ display: 'none' }}
              />
              
              {selectedFile ? (
                <div className="file-selected">
                  <div className="file-icon">📄</div>
                  <div className="file-info">
                    <p className="file-name">{selectedFile.name}</p>
                    <p className="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                  <button
                    type="button"
                    className="remove-file-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveFile();
                    }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <>
                  <div className="upload-icon">☁️</div>
                  <p className="upload-text">Envie seu currículo em PDF</p>
                  <p className="upload-instructions">Clique aqui ou arraste seu arquivo PDF</p>
                  <p className="upload-limit">Tamanho máximo: 10MB</p>
                </>
              )}
            </div>

            <button
              type="submit"
              className="analyze-button"
              disabled={!selectedFile || isUploading}
            >
              {isUploading ? 'Analisando...' : '✓ Analisar Currículo'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default UploadResumePage;