export {
  HttpOllamaClient,
  MockOllamaClient,
  SYSTEM_PROMPT,
  askAssistant,
  createOllamaClient,
  normalizeCitations,
  probeAssistantHealth,
  toolStatusLabel,
  windowHistory,
  type AskAssistantOptions,
  type AssistantAnswer,
  type AssistantHealth,
  type AssistantHistoryTurn,
  type ChatMessage,
  type Citation,
  type OllamaClient,
} from "./assistant-service";
export {
  applyGroundingCaution,
  assessGrounding,
  type GroundingAssessment,
} from "./grounding";
export type {
  ChartReadingContext,
  LifeChapter,
  LifeStory,
  LifeStoryLens,
  ReadingItem,
  ReadingSection,
} from "./reading-context";
export {
  TOOL_ANCHORS,
  TOOL_DEFINITIONS,
  executeTool,
  parseToolArgs,
} from "./tools";
export {
  EVAL_CASES,
  EVAL_FIXTURES,
  EvalMockOllamaClient,
  assertEvalAnswer,
  createEvalClient,
  fixtureById,
  runEvalCase,
  stubReadingForArtifact,
  type EvalCase,
  type EvalExpect,
  type EvalFixture,
  type EvalResult,
  type FixtureId,
} from "./eval/index";
export {
  CLASSICAL_CORPUS,
  classicalPassageById,
  searchClassical,
  type ClassicalHit,
  type ClassicalPassage,
} from "./classical/index";
