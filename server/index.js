import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json({ limit: '5mb' }));

const DATA_FILE = path.join(__dirname, 'data.json');

function ensureDataFile() {
  if (!fs.existsSync(DATA_FILE)) {
    const initialData = {
      credits: 1,
      users: [],
      gallery: [
        {
          id: 1,
          title: 'Y2K Asymmetrical Corset',
          creator: '@skate_sews',
          price: 2.99,
          image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500',
          buys: 14
        },
        {
          id: 2,
          title: 'Cyber Punk Patchwork Top',
          creator: '@neo_threads',
          price: 2.99,
          image: 'https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=500',
          buys: 9
        },
        {
          id: 3,
          title: 'Dreamscape Flared Dress',
          creator: '@y2k_studio',
          price: 2.99,
          image: 'https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=500',
          buys: 22
        }
      ]
    };

    fs.writeFileSync(DATA_FILE, JSON.stringify(initialData, null, 2));
  }
}

function readData() {
  ensureDataFile();
  return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

function writeData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

app.get('/api/health', (req, res) => {
  res.json({ ok: true, service: 'pyfit-backend', timestamp: new Date().toISOString() });
});

app.get('/api/gallery', (req, res) => {
  const data = readData();
  res.json(data.gallery);
});

app.post('/api/auth', (req, res) => {
  const { email } = req.body || {};

  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Valid email is required.' });
  }

  const data = readData();
  const existingUser = data.users.find((user) => user.email.toLowerCase() === email.toLowerCase());

  if (existingUser) {
    return res.json({ user: existingUser, message: 'Welcome back.' });
  }

  const newUser = {
    id: Date.now(),
    email,
    credits: 1,
    createdAt: new Date().toISOString()
  };

  data.users.push(newUser);
  writeData(data);
  res.status(201).json({ user: newUser, message: 'User created.' });
});

app.get('/api/users/:email', (req, res) => {
  const data = readData();
  const user = data.users.find((item) => item.email.toLowerCase() === decodeURIComponent(req.params.email).toLowerCase());

  if (!user) {
    return res.status(404).json({ error: 'User not found.' });
  }

  res.json(user);
});

app.post('/api/subscribe', (req, res) => {
  const { email, creditsToAdd } = req.body || {};

  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Valid email is required.' });
  }

  const data = readData();
  const user = data.users.find((item) => item.email.toLowerCase() === email.toLowerCase());

  if (!user) {
    return res.status(404).json({ error: 'User does not exist.' });
  }

  user.credits += Number(creditsToAdd || 0);
  writeData(data);

  res.json({ user, message: 'Subscription credits updated.' });
});

app.post('/api/gallery/list', (req, res) => {
  const { title, email } = req.body || {};

  if (!title) {
    return res.status(400).json({ error: 'Pattern title is required.' });
  }

  const data = readData();
  const listing = {
    id: Date.now(),
    title,
    creator: email ? `@${email.split('@')[0]}` : '@guest_designer',
    price: 2.99,
    image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500',
    buys: 0
  };

  data.gallery.unshift(listing);
  writeData(data);

  res.status(201).json({ listing, message: 'Pattern listed.' });
});

app.listen(PORT, () => {
  console.log(`PYF backend running on http://localhost:${PORT}`);
});
