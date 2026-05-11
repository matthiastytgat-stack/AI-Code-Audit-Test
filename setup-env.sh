#!/bin/bash

# Setup script for Django-Next.js Chatbot
# This script creates .env file from .env.example

echo "🚀 Setting up environment files for Django-Next.js Chatbot..."
echo ""

# Check if .env already exists
if [ -f ".env" ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled. Keeping existing .env file."
        exit 0
    fi
fi

# Copy .env.example to .env
cp .env.example .env
echo "✅ Created .env file from .env.example"

# Prompt for OpenAI API key
echo ""
echo "📝 Please enter your API keys:"
echo ""
read -p "OpenAI API Key (required): " openai_key

if [ ! -z "$openai_key" ]; then
    # Use different sed syntax for macOS vs Linux
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/OPENAI_API_KEY=your-openai-api-key-here/OPENAI_API_KEY=$openai_key/" .env
    else
        # Linux/WSL
        sed -i "s/OPENAI_API_KEY=your-openai-api-key-here/OPENAI_API_KEY=$openai_key/" .env
    fi
    echo "✅ OpenAI API key added"
else
    echo "⚠️  No OpenAI API key provided. You'll need to add it manually to .env"
fi

# Prompt for Tavily API key (optional)
read -p "Tavily API Key (optional, press Enter to skip): " tavily_key

if [ ! -z "$tavily_key" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/TAVILY_API_KEY=your-tavily-api-key-here/TAVILY_API_KEY=$tavily_key/" .env
    else
        sed -i "s/TAVILY_API_KEY=your-tavily-api-key-here/TAVILY_API_KEY=$tavily_key/" .env
    fi
    echo "✅ Tavily API key added"
else
    echo "ℹ️  Tavily API key skipped (optional)"
fi

echo ""
echo "✅ Environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Review .env file and adjust settings if needed"
echo "   2. Run: docker compose up --build"
echo "   3. Open http://localhost:3000 in your browser"
echo ""
echo "🎉 Happy coding!"
