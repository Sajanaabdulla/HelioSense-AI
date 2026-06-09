-- MySQL schema for Helia AI
CREATE DATABASE IF NOT EXISTS heliosense_ai;
USE heliosense_ai;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128),
  email VARCHAR(256) UNIQUE,
  phone VARCHAR(32),
  location VARCHAR(256),
  password_hash VARCHAR(256),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  latitude FLOAT,
  longitude FLOAT,
  monthly_bill FLOAT,
  roof_type VARCHAR(64),
  roof_area FLOAT,
  roof_orientation VARCHAR(64),
  roof_tilt FLOAT,
  shading_percent FLOAT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS predictions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  assessment_id INT,
  solar_score INT,
  peak_sun_hours FLOAT,
  annual_generation_kwh FLOAT,
  recommended_capacity_kw FLOAT,
  recommended_panels INT,
  roof_suitability VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id)
);

CREATE TABLE IF NOT EXISTS roi_analysis (
  id INT AUTO_INCREMENT PRIMARY KEY,
  prediction_id INT,
  system_cost FLOAT,
  electricity_tariff FLOAT,
  subsidy FLOAT,
  panel_efficiency FLOAT,
  annual_savings FLOAT,
  monthly_savings FLOAT,
  payback_years FLOAT,
  roi_percent FLOAT,
  lifetime_savings FLOAT,
  co2_reduction_kg FLOAT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (prediction_id) REFERENCES predictions(id)
);

CREATE TABLE IF NOT EXISTS chat_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  question TEXT,
  answer TEXT,
  metadata TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(256),
  path VARCHAR(512),
  uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  assessment_id INT,
  path VARCHAR(512),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
