import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import logo from '../assets/div.svg';
import emailLogo from '../assets/Vector.svg';
import passwordLogo from '../assets/pass.svg';
import caba from '../assets/caba.svg';
import { registerUser, loginUser } from '../services/authService'; 
import './RegisterPage.css';

const RegisterPage = ({ onForgotPassword }) => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      // 1. Registra o usuário
      await registerUser(email, name, password);
      
      // 2. Faz login automaticamente após registro
      try {
        const loginResponse = await loginUser(email, password);
        const user = loginResponse.data;
        const tokens = loginResponse.tokens;

        // Guarda os tokens corretamente
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);

        // Salva o user como JSON
        localStorage.setItem('user', JSON.stringify(user));

        alert('Cadastro realizado com sucesso! Você será redirecionado...');
        window.location.href = '/home';
      } catch (loginErr) {
        // Se o login falhar, apenas redireciona para a página de login
        console.error('Erro ao fazer login automático:', loginErr);
        alert('Cadastro realizado com sucesso! Faça login para continuar.');
        window.location.href = '/login';
      }

    } catch (err) {
      console.error('Erro no cadastro:', err);
      const errorMessage = err.message || 'Erro ao cadastrar. Verifique os dados e tente novamente.';

      setError(errorMessage);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className='logo-box'>
            <img src={logo} alt="Logo" />
          </div>
          <h1>Cadastro</h1>
          <p className="subtitle">Preencha os dados abaixo para criar sua conta.</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <p className="error">{error}</p>}

          <div className="form-group">
            <label className="form-label">Nome</label>
            <div className="input-icon-container">
              <img src={caba} alt="ícone de e-mail" className="input-icon" />
              <input
                type="name"
                className="form-input"
                placeholder="Digite seu nome completo"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">E-mail</label>
            <div className="input-icon-container">
              <img src={emailLogo} alt="ícone de e-mail" className="input-icon" />
              <input
                type="email"
                className="form-input"
                placeholder="Digite seu e-mail"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Senha</label>
            <div className="input-icon-container">
              <img src={passwordLogo} alt="ícone de senha" className="input-icon" />
              <input
                type="password"
                className="form-input"
                placeholder="Digite sua senha"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button type="submit" className="login-button">Cadastrar</button>
        </form>

        <div className="signup-section">
          <p className="signup-text">Já tem uma conta?</p>
          <button type="button" className="signup-button" onClick={() => navigate("/login")}>Fazer login</button>
        </div>

        <footer className="footer">
          <p>&copy; 2025 CareerPath-AI. Todos os direitos reservados.</p>
        </footer>
      </div>
    </div>
  );
};

export default RegisterPage;
