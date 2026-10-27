// VocationalFormPage.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import logo from '../assets/div.svg';
import UserProfile from '../components/UserProfile';
import { createDevelopmentTrail } from '../services/authService';
import './VocationalFormPage.css';

const VocationalFormPage = () => {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user")) || { name: "Usuário" };
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const totalSteps = 12;

  const [formData, setFormData] = useState({
    name: '',
    age: '',
    education: '',
    current_area: '',
    experience_in_years: '',
    skills: '',
    interested_technologies: '',
    current_level: '',
    professional_goal: '',
    available_time_week: '',
    goal_timeframe: '',
    additional_information: ''
  });

  const educationOptions = [
    'Ensino Médio',
    'Graduação em andamento',
    'Graduação completa',
    'Pós-graduação',
    'Mestrado',
    'Doutorado'
  ];

  const levelOptions = ['Iniciante', 'Intermediário', 'Avançado'];
  const timeOptions = ['Até 10 horas', '10-20 horas', 'Mais de 20 horas'];

  const questions = [
    {
      id: 1,
      title: 'Qual é o seu nome completo?',
      field: 'name',
      type: 'text',
      placeholder: 'Digite seu nome completo...'
    },
    {
      id: 2,
      title: 'Qual é a sua idade?',
      field: 'age',
      type: 'number',
      placeholder: 'Digite sua idade...'
    },
    {
      id: 3,
      title: 'Qual é o seu nível de educação?',
      field: 'education',
      type: 'select',
      options: educationOptions,
      placeholder: 'Selecione sua formação...'
    },
    {
      id: 4,
      title: 'Qual é sua área atual de atuação/estudo?',
      field: 'current_area',
      type: 'text',
      placeholder: 'Ex: Estudante de TI, Profissional de Marketing...'
    },
    {
      id: 5,
      title: 'Quantos anos de experiência você tem na área?',
      field: 'experience_in_years',
      type: 'number',
      placeholder: 'Digite o número de anos...'
    },
    {
      id: 6,
      title: 'Quais são suas principais habilidades?',
      field: 'skills',
      type: 'textarea',
      placeholder: 'Separe por vírgula (Ex: Python, SQL, Git, React...)'
    },
    {
      id: 7,
      title: 'Quais tecnologias/áreas te interessam?',
      field: 'interested_technologies',
      type: 'textarea',
      placeholder: 'Separe por vírgula (Ex: Back-End, Data Science, Front-End, DevOps...)'
    },
    {
      id: 8,
      title: 'Qual é o seu nível atual de conhecimento?',
      field: 'current_level',
      type: 'select',
      options: levelOptions,
      placeholder: 'Selecione seu nível...'
    },
    {
      id: 9,
      title: 'Qual é o seu objetivo profissional principal?',
      field: 'professional_goal',
      type: 'textarea',
      placeholder: 'Ex: Desenvolvimento Back-End, Análise de Dados, UX/UI Design...'
    },
    {
      id: 10,
      title: 'Quanto tempo você tem disponível por semana para estudos?',
      field: 'available_time_week',
      type: 'select',
      options: timeOptions,
      placeholder: 'Selecione o tempo disponível...'
    },
    {
      id: 11,
      title: 'Em quanto tempo você gostaria de atingir seu objetivo?',
      field: 'goal_timeframe',
      type: 'text',
      placeholder: 'Ex: Conseguir estágio em até 6 meses, Trocar de área em 1 ano...'
    },
    {
      id: 12,
      title: 'Informações adicionais (opcional)',
      field: 'additional_information',
      type: 'textarea',
      placeholder: 'Compartilhe mais detalhes sobre seus interesses, objetivos ou dúvidas...'
    }
  ];

  const currentQuestion = questions[currentStep - 1];

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (isSubmitting) return; // Previne múltiplos submits
    
    setIsSubmitting(true);
    
    // Preparar os dados para enviar ao backend
    const submissionData = {
      ...formData,
      skills: formData.skills.split(',').map(skill => skill.trim()).filter(skill => skill),
      interested_technologies: formData.interested_technologies.split(',').map(tech => tech.trim()).filter(tech => tech),
      experience_in_years: parseInt(formData.experience_in_years) || 0,
      age: parseInt(formData.age) || 0
    };

    try {
      const response = await createDevelopmentTrail(submissionData);
      
      // Redireciona para a trilha criada
      navigate(`/trail/${response.id}`);
      
    } catch (error) {
      console.error('Erro ao gerar trilha:', error);
      
      // Mensagem de erro mais específica
      let errorMessage = 'Erro ao gerar trilha de estudos. Tente novamente.';
      
      if (error.status === 429) {
        errorMessage = 'Limite de uso da API do Gemini excedido. Por favor, aguarde alguns minutos e tente novamente. O plano gratuito tem limites reduzidos.';
      } else if (error.message && error.message.includes('authentication')) {
        errorMessage = 'Erro de autenticação. Verifique a configuração da API.';
      }
      
      alert(errorMessage);
      setIsSubmitting(false); // Reabilita o botão em caso de erro
    }
  };

  const progressPercentage = (currentStep / totalSteps) * 100;

  const renderInputField = () => {
    switch (currentQuestion.type) {
      case 'textarea':
        return (
          <textarea
            name={currentQuestion.field}
            value={formData[currentQuestion.field]}
            onChange={handleInputChange}
            className="form-textarea"
            placeholder={currentQuestion.placeholder}
            rows={4}
            required={currentStep !== 12}
          />
        );
      
      case 'select':
        return (
          <select
            name={currentQuestion.field}
            value={formData[currentQuestion.field]}
            onChange={handleInputChange}
            className="form-select"
            required={currentStep !== 12}
          >
            <option value="">{currentQuestion.placeholder}</option>
            {currentQuestion.options.map((option, index) => (
              <option key={index} value={option}>{option}</option>
            ))}
          </select>
        );
      
      default:
        return (
          <input
            type={currentQuestion.type}
            name={currentQuestion.field}
            value={formData[currentQuestion.field]}
            onChange={handleInputChange}
            className="form-input"
            placeholder={currentQuestion.placeholder}
            required={currentStep !== 12}
          />
        );
    }
  };

  const handleLogout = async () => {
    const { handleLogout: logoutHelper } = await import('../utils/logoutHelper');
    await logoutHelper();
  };

  return (
    <div className="vocational-form-container">
      <header className="upload-header">
        <div 
          className="header-left" 
          onClick={() => navigate("/home")} 
          style={{ cursor: 'pointer' }}
        >
          <div className="logo-box-header">
            <img src={logo} alt="Logo" />
          </div>
          <span className="app-name">CareerPathAI</span>
        </div>

        <nav className="header-nav">
          <UserProfile user={user} onLogout={handleLogout} />
        </nav>
      </header>

      <main className="vocational-form-main">
        <div className="form-card">

            {/* Cabeçalho sem barra de progresso */}
            <div className="form-header">
            <h1 className="form-title">Defina sua Rota Profissional</h1>
            <p className="form-subtitle">
                Responda às perguntas abaixo para criarmos sua trilha de estudos personalizada.
            </p>
            </div>

            {/* Formulário */}
            <form
            className="vocational-form"
            onSubmit={
                currentStep === totalSteps
                ? handleSubmit
                : (e) => {
                    e.preventDefault();
                    handleNext();
                    }
            }
            >
            <div className="question-container">
                <h2 className="question-title">{currentQuestion.title}</h2>

                <div className="input-container">
                {renderInputField()}
                </div>
            </div>

            {/* Navegação com botões circulares */}
            <div className="navigation-buttons">
                {/* Botão voltar */}
                <button
                type="button"
                className="nav-circle-btn"
                onClick={handleBack}
                disabled={currentStep === 1}
                >
                ❮
                </button>

                {/* Indicador de passo central */}
                <span className="step-counter-bottom">
                {currentStep} de {totalSteps}
                </span>

                {/* Botão próximo ou enviar */}
                {currentStep === totalSteps ? (
                <button 
                  type="submit" 
                  className="nav-circle-btn"
                  disabled={isSubmitting}
                  style={{
                    opacity: isSubmitting ? 0.8 : 1,
                    cursor: isSubmitting ? 'wait' : 'pointer',
                    position: 'relative'
                  }}
                >
                  {isSubmitting ? (
                    <span style={{ 
                      display: 'inline-block',
                      width: '18px',
                      height: '18px',
                      border: '2px solid rgba(255, 255, 255, 0.3)',
                      borderTop: '2px solid #ffffff',
                      borderRadius: '50%',
                      animation: 'spin 0.8s linear infinite'
                    }}></span>
                  ) : (
                    '✓'
                  )}
                </button>
                ) : (
                <button type="submit" className="nav-circle-btn">
                    ❯
                </button>
                )}
            </div>
            </form>
        </div>
        </main>
    </div>
  );
};

export default VocationalFormPage;