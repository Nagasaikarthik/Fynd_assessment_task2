# Fynd_assessment_task


This task contains two tasks demonstrating prompt engineering, LLM evaluation, and AI-powered feedback generation.

Task-1: LLM Prompt Evaluation (Yelp Reviews)

Task-1 evaluates how different prompting strategies affect the performance of a Large Language Model when predicting star ratings from Yelp reviews.
Three prompt versions were designed and tested:

Direct Prompt

Chain-of-Thought Prompt

Few-Shot Prompt

Each prompt was evaluated on ~200 reviews using metrics such as:

Accuracy (predicted vs actual rating)

JSON Validity (whether the model produced valid JSON output)

Consistency (whether repeated runs return the same answer)

The Few-Shot prompt produced the most reliable and well-formatted JSON outputs, while Chain-of-Thought achieved the highest accuracy.

Task-2: AI-Powered User Feedback System

Task-2 implements a simple application where:

Users submit a rating and review

The AI generates a response, summary, and sentiment check

Admins log in with a username and password to view stored feedback

The system uses Gemini LLM to generate structured JSON responses and stores all submissions in CSV/JSON for later analysis.

Overall

Across both tasks, prompt engineering played a critical role in improving:

Output quality

Format stability

LLM reasoning

Real-world usability

Few-Shot prompts were best for structure, Chain-of-Thought for reasoning, and Direct prompts served as the baseline.
