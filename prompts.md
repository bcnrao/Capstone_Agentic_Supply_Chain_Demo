# Prompt 1 - Create README.md file

Read the file "Agentic supply chain disruption and predictor.pdf" file in the docs folder and create a README.md file.

# Prompt 2
We are building an AI-powered supply chain disruption prediction and simulation system. Look in the README.md for the detailed project description.

Let's create a "constitution" in a specs directory:

- mission.md
- tech-stack.md
- roadmap.md for high-level implementation order, in very small phases of work.

Important: You must use your AskUserQuestion tool, grouped on these 3, before writing to disk.

# Prompt 3
Find the next phase on specs/roadmap.md and make a branch, ask me about the feature spec. Create:

A new directory YYYY-MM-DD-feature-name under specs for this feature work
In there:
plan.md as a series of numbered task groups.
requirements.md for the scope, decisions, context
validation.md for how to know the implementation succeeded and can be merged
Refer to specs/mission.md and specs/tech-stack.md for guidance.

Important: You must use your AskUserQuestion tool, grouped on these 3, before writing to disk.

# Prompt 4
Implement the remaining task groups.

# Prompt 5
Mark this specs/roadmap.md phase as complete, commit this work, switch to main, and merge this branch, then delete it.