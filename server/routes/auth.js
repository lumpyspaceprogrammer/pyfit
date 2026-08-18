import express from 'express';
import bcrypt from 'bcryptjs';
import { query } from '../database/db.js';
import { generateToken } from '../middleware/auth.js';

const router = express.Router();

// Sign Up
router.post('/signup', async (req, res) => {
  try {
    const { email, password, username } = req.body;

    // Validate input
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    // Check if user already exists
    const existingUser = await query('SELECT id FROM users WHERE email = ?', [email]);
    if (existingUser.length > 0) {
      return res.status(400).json({ error: 'Email already registered' });
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, 10);

    // Create user
    const result = await query(
      'INSERT INTO users (email, password_hash, username) VALUES (?, ?, ?)',
      [email, passwordHash, username || email.split('@')[0]]
    );

    const userId = result.insertId;

    // Create user credits record (1 free credit)
    await query(
      'INSERT INTO user_credits (user_id, credits, subscription_tier) VALUES (?, ?, ?)',
      [userId, 1, 'free']
    );

    // Generate token
    const token = generateToken(userId, email);

    res.status(201).json({
      success: true,
      message: 'User created successfully',
      token,
      user: {
        id: userId,
        email,
        username: username || email.split('@')[0],
        credits: 1
      }
    });
  } catch (error) {
    console.error('Signup error:', error);
    res.status(500).json({ error: 'Server error during signup' });
  }
});

// Login
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    // Validate input
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    // Find user
    const users = await query('SELECT id, email, password_hash, username FROM users WHERE email = ?', [email]);
    if (users.length === 0) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    const user = users[0];

    // Verify password
    const isValid = await bcrypt.compare(password, user.password_hash);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    // Get user credits
    const credits = await query('SELECT credits FROM user_credits WHERE user_id = ?', [user.id]);
    const userCredits = credits.length > 0 ? credits[0].credits : 0;

    // Generate token
    const token = generateToken(user.id, user.email);

    res.json({
      success: true,
      token,
      user: {
        id: user.id,
        email: user.email,
        username: user.username,
        credits: userCredits
      }
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Server error during login' });
  }
});

export default router;
