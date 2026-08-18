import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

/**
 * AI Vision Service
 * Analyzes clothing photos to extract garment features
 * Uses Hugging Face API for image classification
 */

// Using Hugging Face's free image classification model
const HUGGINGFACE_API_URL = 'https://api-inference.huggingface.co/models/google/vit-base-patch16-224';

/**
 * Analyze uploaded image to detect garment type and features
 * @param {string} imageBase64 - Image in base64 format
 * @returns {Object} - Detected garment features
 */
export const analyzeGarmentImage = async (imageBase64) => {
  try {
    // For demo purposes, return mock data
    // In production, you'd call the actual API with your HuggingFace API key
    
    if (process.env.HUGGINGFACE_API_KEY) {
      // Real API call (commented out for safety)
      // const response = await axios.post(
      //   HUGGINGFACE_API_URL,
      //   imageBase64,
      //   {
      //     headers: {
      //       Authorization: `Bearer ${process.env.HUGGINGFACE_API_KEY}`,
      //       'Content-Type': 'application/json',
      //     },
      //   }
      // );
      // return processVisionResponse(response.data);
    }

    // Mock analysis for development
    return {
      garment_type: 'dress',
      detected_features: {
        neckline: 'sweetheart',
        sleeves: 'cap',
        fit: 'fitted',
        hem_style: 'flared',
        material_estimate: 'cotton blend'
      },
      confidence: 0.87
    };
  } catch (error) {
    console.error('Vision analysis error:', error);
    throw new Error('Failed to analyze image');
  }
};

/**
 * Process vision API response and extract garment features
 * @param {Object} visionData - Raw response from vision API
 * @returns {Object} - Structured garment features
 */
const processVisionResponse = (visionData) => {
  // Parse the vision API response and extract relevant clothing features
  const features = {
    garment_type: extractGarmentType(visionData),
    detected_features: extractClothingFeatures(visionData),
    confidence: extractConfidence(visionData)
  };

  return features;
};

/**
 * Extract garment type from vision data
 * Options: dress, top, pants, skirt, jacket, etc.
 */
const extractGarmentType = (visionData) => {
  // Parse vision data to determine garment type
  const labels = visionData.map(item => item.label?.toLowerCase() || '');
  
  if (labels.some(l => l.includes('dress'))) return 'dress';
  if (labels.some(l => l.includes('shirt') || l.includes('top'))) return 'top';
  if (labels.some(l => l.includes('pant') || l.includes('trouser'))) return 'pants';
  if (labels.some(l => l.includes('skirt'))) return 'skirt';
  if (labels.some(l => l.includes('jacket'))) return 'jacket';
  
  return 'top'; // default
};

/**
 * Extract specific clothing features (neckline, sleeves, fit, etc.)
 */
const extractClothingFeatures = (visionData) => {
  return {
    neckline: 'round',
    sleeves: 'short',
    fit: 'fitted',
    hem_style: 'straight',
    material_estimate: 'unknown'
  };
};

/**
 * Extract confidence score
 */
const extractConfidence = (visionData) => {
  if (Array.isArray(visionData) && visionData.length > 0) {
    return visionData[0].score || 0.5;
  }
  return 0.5;
};

export default analyzeGarmentImage;
