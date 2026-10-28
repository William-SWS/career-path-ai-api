import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Header from '../components/Header'; // Importando o Header component
import { getDevelopmentTrailById } from '../services/authService';
import { API_URL } from '../config';
import jsPDF from 'jspdf';
import './DevelopmentTrailPage.css';

const DevelopmentTrailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [trail, setTrail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const user = JSON.parse(localStorage.getItem('user') || '{"name": "Usuário"}');

  const handleLogout = async () => {
    const { handleLogout: logoutHelper } = await import('../utils/logoutHelper');
    await logoutHelper();
  };

  useEffect(() => {
    const fetchTrail = async () => {
      try {
        setLoading(true);
        setError('');
        
        // Verifica se há token de autenticação
        const token = localStorage.getItem('access_token');
        if (!token) {
          setError('Você precisa estar autenticado para ver esta trilha. Faça login primeiro.');
          setLoading(false);
          return;
        }

        const data = await getDevelopmentTrailById(id);
        setTrail(data);
      } catch (err) {
        console.error('Erro ao buscar trilha:', err);
        console.error('Detalhes do erro:', {
          message: err.message,
          status: err.status,
          id: id
        });
        
        // Mensagens de erro mais específicas
        if (err.status === 404 || err.message.includes('404') || err.message.includes('não encontrada')) {
          setError(`Trilha com ID ${id} não encontrada. Verifique se o ID está correto ou se você tem acesso a esta trilha.`);
        } else if (err.status === 401 || err.message.includes('401') || err.message.includes('não autorizado') || err.message.includes('Token')) {
          setError('Você não tem permissão para acessar esta trilha. Faça login novamente.');
        } else if (err.status === 403 || err.message.includes('403')) {
          setError('Acesso negado. Esta trilha pertence a outro usuário.');
        } else if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
          setError(`Erro de conexão com o servidor. Verifique se o backend está rodando em ${API_URL}`);
        } else {
          setError(`Erro ao carregar trilha: ${err.message || 'Erro desconhecido'}. Verifique o console para mais detalhes.`);
        }
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchTrail();
    } else {
      setError('ID da trilha não fornecido');
      setLoading(false);
    }
  }, [id]);

  const handleNewForm = () => {
    navigate('/vocational-form');
  };

  const handleExportPDF = () => {
    if (!trail) {
      alert('Erro: Trilha não carregada');
      return;
    }

    const developmentData = trail.development_trail || {};
    const weeks = formatWeeks(developmentData.development_phases || []);

    try {
      const doc = new jsPDF();
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 20;
      const maxWidth = pageWidth - (margin * 2);
      let yPosition = margin;

      // Função auxiliar para adicionar nova página se necessário
      const checkPageBreak = (requiredSpace = 20) => {
        if (yPosition + requiredSpace > pageHeight - margin) {
          doc.addPage();
          yPosition = margin;
          return true;
        }
        return false;
      };

      // Função para adicionar texto com quebra de linha
      const addText = (text, fontSize = 10, isBold = false, color = [0, 0, 0]) => {
        doc.setFontSize(fontSize);
        doc.setTextColor(color[0], color[1], color[2]);
        if (isBold) {
          doc.setFont(undefined, 'bold');
        } else {
          doc.setFont(undefined, 'normal');
        }
        
        const lines = doc.splitTextToSize(text, maxWidth);
        
        checkPageBreak(lines.length * (fontSize * 0.5) + 5);
        
        lines.forEach(line => {
          if (yPosition + fontSize * 0.5 > pageHeight - margin) {
            doc.addPage();
            yPosition = margin;
          }
          doc.text(line, margin, yPosition);
          yPosition += fontSize * 0.5 + 2;
        });
        
        yPosition += 3;
      };

      // Cabeçalho
      doc.setFillColor(59, 130, 246); // Azul
      doc.rect(0, 0, pageWidth, 40, 'F');
      
      doc.setTextColor(255, 255, 255);
      doc.setFontSize(20);
      doc.setFont(undefined, 'bold');
      doc.text('Plano de Desenvolvimento Personalizado', margin, 25);
      
      yPosition = 50;

      // Informações do perfil
      if (developmentData.user_profile_summary) {
        const profile = developmentData.user_profile_summary;
        
        addText('INFORMAÇÕES DO PERFIL', 14, true, [59, 130, 246]);
        yPosition += 2;
        
        if (profile.professional_goal) {
          addText(`Objetivo Profissional: ${profile.professional_goal}`, 11, true);
        }
        
        if (profile.current_level) {
          addText(`Nível Atual: ${profile.current_level}`, 10);
        }
        
        if (profile.goal_timeframe) {
          addText(`Prazo Estimado: ${profile.goal_timeframe}`, 10);
        }
        
        yPosition += 5;
      }

      // Semanas
      if (weeks && weeks.length > 0) {
        addText('PLANO SEMANAL DE ESTUDOS', 14, true, [59, 130, 246]);
        yPosition += 5;

        weeks.forEach((week, weekIndex) => {
          checkPageBreak(50);
          
          // Título da semana
          doc.setFillColor(139, 92, 246); // Roxo
          doc.roundedRect(margin, yPosition - 8, maxWidth, 15, 3, 3, 'F');
          
          doc.setTextColor(255, 255, 255);
          doc.setFontSize(14);
          doc.setFont(undefined, 'bold');
          doc.text(`SEMANA ${week.weekNumber}`, margin + 5, yPosition);
          
          yPosition += 12;
          doc.setTextColor(0, 0, 0);

          // Foco da semana
          if (week.focus) {
            addText(`Foco: ${week.focus}`, 11, true, [100, 100, 100]);
          }

          // Tópicos
          if (week.topics && week.topics.length > 0) {
            addText('Tópicos de Estudo:', 11, true);
            week.topics.forEach(topic => {
              const parts = topic.split(/ - |: /);
              const title = parts[0];
              const description = parts.length > 1 ? parts.slice(1).join(' - ') : '';
              const fullText = description ? `${title} - ${description}` : title;
              addText(`  • ${fullText}`, 10);
            });
          }

          // Projetos
          if (week.projects && week.projects.length > 0) {
            addText('Projetos Práticos:', 11, true);
            week.projects.forEach(project => {
              addText(`  • ${project}`, 10);
            });
          }

          // Resultados Esperados
          if (week.learningOutcomes && week.learningOutcomes.length > 0) {
            addText('Resultados Esperados:', 11, true);
            week.learningOutcomes.forEach(outcome => {
              addText(`  • ${outcome}`, 10);
            });
          }

          // Espaço entre semanas (exceto na última)
          if (weekIndex < weeks.length - 1) {
            yPosition += 5;
            doc.setDrawColor(200, 200, 200);
            doc.line(margin, yPosition, pageWidth - margin, yPosition);
            yPosition += 10;
          }
        });
      }

      // Rodapé
      const totalPages = doc.internal.pages.length - 1;
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.text(
          `Página ${i} de ${totalPages} - CareerPathAI`,
          pageWidth - margin - 60,
          pageHeight - 10
        );
        doc.text(
          `Gerado em ${new Date().toLocaleDateString('pt-BR')}`,
          margin,
          pageHeight - 10
        );
      }

      // Salvar PDF
      const fileName = `Trilha_Desenvolvimento_${trail.id}_${new Date().toISOString().split('T')[0]}.pdf`;
      doc.save(fileName);
    } catch (error) {
      console.error('Erro ao gerar PDF:', error);
      alert('Erro ao gerar PDF. Por favor, tente novamente.');
    }
  };

  const formatWeeks = (developmentPhases) => {
    if (!developmentPhases || !Array.isArray(developmentPhases)) {
      return [];
    }

    // Converte fases em semanas
    const weeks = [];
    let weekNumber = 1;

    developmentPhases.forEach((phase, index) => {
      // Extrai duração da fase (ex: "2-3 semanas" ou "2 meses")
      const duration = phase.duration || '';
      const weeksMatch = duration.match(/(\d+)\s*semanas?/i);
      const monthsMatch = duration.match(/(\d+)\s*meses?/i);
      
      let phaseWeeks = 1;
      if (weeksMatch) {
        phaseWeeks = parseInt(weeksMatch[1]);
      } else if (monthsMatch) {
        phaseWeeks = parseInt(monthsMatch[1]) * 4; // Aproximação: 1 mês = 4 semanas
      }

      // Cria semanas baseadas na fase
      for (let i = 0; i < phaseWeeks && weekNumber <= 6; i++) {
        weeks.push({
          weekNumber: weekNumber,
          phase: phase.phase || `Fase ${index + 1}`,
          focus: phase.focus || '',
          topics: phase.topics || [],
          projects: phase.projects || [],
          learningOutcomes: phase.learning_outcomes || [],
        });
        weekNumber++;
      }
    });

    // Preenche até 6 semanas se necessário
    while (weeks.length < 6) {
      weeks.push({
        weekNumber: weeks.length + 1,
        phase: 'Consolidação',
        focus: 'Revisão e prática',
        topics: ['Revisão dos tópicos anteriores'],
        projects: ['Projeto de consolidação'],
        learningOutcomes: ['Aplicação prática dos conhecimentos'],
      });
    }

    return weeks.slice(0, 6); // Garante máximo de 6 semanas
  };

  if (loading) {
    return (
      <div className="trail-container">
        <Header user={user} onLogout={handleLogout} />
        <div className="loading-message">Carregando trilha de desenvolvimento...</div>
      </div>
    );
  }

  if (error || !trail) {
    return (
      <div className="trail-container">
        <Header user={user} onLogout={handleLogout} />
        <div className="trail-content-wrapper">
          <main className="trail-main">
            <div className="trail-card">
              <div className="error-message-container">
                <h2 className="error-title">Erro ao carregar trilha</h2>
                <p className="error-text">{error || 'Trilha não encontrada'}</p>
                <div className="error-actions">
                  <button className="error-btn" onClick={() => navigate('/home')}>
                    Voltar para Home
                  </button>
                  <button className="error-btn secondary" onClick={() => window.location.reload()}>
                    Tentar Novamente
                  </button>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const developmentData = trail.development_trail || {};
  const weeks = formatWeeks(developmentData.development_phases || []);

  return (
    <div className="trail-container">
      {/* Header component */}
      <Header user={user} onLogout={handleLogout} />

      {/* Main Content */}
      <main className="trail-main">
        <div className="trail-card">
          <div className="trail-card-header">
            <h1 className="trail-title">Plano de Desenvolvimento Personalizado</h1>
            {developmentData.user_profile_summary && (
              <p className="trail-subtitle">
                {developmentData.user_profile_summary.current_profile || 
                 'Trilha de estudos personalizada para acelerar sua carreira'}
              </p>
            )}
          </div>

          <div className="weeks-container">
            {weeks.map((week, index) => (
              <div key={index} className="week-card">
                <div className="week-header">
                  <div className="week-icon">📅</div>
                  <h2 className="week-title">Semana {week.weekNumber}</h2>
                </div>
                
                {week.focus && (
                  <p className="week-focus">{week.focus}</p>
                )}

                {week.topics && week.topics.length > 0 && (
                  <div className="week-content">
                    <h3 className="content-title">Tópicos:</h3>
                    <ul className="content-list">
                      {week.topics.map((topic, topicIndex) => {
                        // Se o tópico tem " - " ou ": ", separa título e descrição
                        const parts = topic.split(/ - |: /);
                        const title = parts[0];
                        const description = parts.length > 1 ? parts.slice(1).join(' - ') : '';
                        return (
                          <li key={topicIndex} className="topic-item">
                            <span className="bullet blue"></span>
                            <span className="item-text">
                              <strong>{title}</strong>
                              {description && ` - ${description}`}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                {week.projects && week.projects.length > 0 && (
                  <div className="week-content">
                    <h3 className="content-title">Projetos Práticos:</h3>
                    <ul className="content-list">
                      {week.projects.map((project, projectIndex) => {
                        const isFinalProject = project.toLowerCase().includes('final') || project.toLowerCase().includes('completa');
                        return (
                          <li key={projectIndex} className="project-item">
                            <span className={`bullet ${isFinalProject ? 'orange' : 'green'}`}></span>
                            <span className="item-text">{project}</span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                {week.learningOutcomes && week.learningOutcomes.length > 0 && (
                  <div className="week-content">
                    <h3 className="content-title">Resultados Esperados:</h3>
                    <ul className="content-list">
                      {week.learningOutcomes.map((outcome, outcomeIndex) => (
                        <li key={outcomeIndex} className="outcome-item">
                          <span className="bullet blue"></span>
                          <span className="item-text">{outcome}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="trail-actions">
            <button className="export-btn" onClick={handleExportPDF}>
              📄 Exportar Plano em PDF
            </button>
            <button className="new-form-btn" onClick={handleNewForm}>
              + Novo Formulário
            </button>
          </div>

          <p className="trail-footer-text">
            Baixe seu plano personalizado para acompanhar offline
          </p>
        </div>
      </main>
    </div>
  );
};

export default DevelopmentTrailPage;