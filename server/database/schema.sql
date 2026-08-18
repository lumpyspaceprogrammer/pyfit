-- PyFit Database Schema
-- Run this SQL to set up your database

CREATE DATABASE IF NOT EXISTS pyfit_db;
USE pyfit_db;

-- Users Table
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  username VARCHAR(100) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- User Credits Table (for subscription management)
CREATE TABLE user_credits (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  credits INT DEFAULT 1,
  subscription_tier VARCHAR(50) DEFAULT 'free', -- free, tier1, tier2, tier3
  subscription_expires_at DATETIME,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Garment/Pattern Records Table
CREATE TABLE patterns (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(255),
  description TEXT,
  
  -- Original Image Data
  image_url VARCHAR(500),
  original_prompt TEXT,
  
  -- AI Vision Analysis Results
  garment_type VARCHAR(100), -- 'dress', 'top', 'pants', etc
  detected_features JSON, -- {neckline: 'sweetheart', sleeves: 'cap', fit: 'fitted'}
  
  -- 3D Mesh Parameters
  mesh_flare FLOAT DEFAULT 0.35,
  mesh_waist_radius FLOAT DEFAULT 0.65,
  mesh_top_height FLOAT DEFAULT 1.8,
  
  -- User Refinements
  refinement_prompts JSON, -- Array of user refinement requests
  
  -- Body Measurements (in cm)
  bust FLOAT,
  waist FLOAT,
  hip FLOAT,
  shoulder_width FLOAT,
  nape_to_waist FLOAT,
  garment_length FLOAT,
  
  -- Generated Pattern Data
  pattern_svg TEXT, -- SVG pattern pieces
  pattern_pdf_url VARCHAR(500),
  seam_allowance_cm FLOAT DEFAULT 1.5,
  grainlines JSON, -- Direction and angle data
  construction_notes JSON, -- Step-by-step sewing instructions
  
  -- Gallery/Marketplace
  is_published BOOLEAN DEFAULT FALSE,
  price FLOAT DEFAULT 2.99,
  purchase_count INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id),
  INDEX idx_published (is_published)
);

-- Pattern Purchases Table (for marketplace)
CREATE TABLE pattern_purchases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pattern_id INT NOT NULL,
  buyer_user_id INT NOT NULL,
  seller_user_id INT NOT NULL,
  price FLOAT DEFAULT 2.99,
  purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (seller_user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_pattern_id (pattern_id),
  INDEX idx_buyer_id (buyer_user_id)
);

-- Credit Transactions Table (for tracking credit usage)
CREATE TABLE credit_transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  amount INT,
  transaction_type VARCHAR(50), -- 'pattern_generation', 'pattern_purchase', 'subscription_bonus'
  description VARCHAR(255),
  pattern_id INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE SET NULL,
  INDEX idx_user_id (user_id)
);

-- Sessions/API Tokens Table
CREATE TABLE sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash VARCHAR(255) UNIQUE NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_id (user_id)
);
