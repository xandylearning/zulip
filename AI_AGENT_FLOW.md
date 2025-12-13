# AI Agent Core - Complete Flow Diagram

## Main Processing Flow

```mermaid
flowchart TD
    Start([Student Sends Message to Mentor]) --> Validate{Is Student→Mentor DM?}
    Validate -->|No| NormalFlow[Normal Message Processing]
    Validate -->|Yes| QueueEvent[Queue AI Agent Conversation Event]
    
    QueueEvent --> Worker[AI Mentor Worker]
    Worker --> EventListener[Event Listener: handle_ai_agent_conversation]
    EventListener --> Orchestrator[AI Agent Orchestrator]
    
    Orchestrator --> QuickChecks[Quick Pre-Checks]
    QuickChecks --> Check1{Mentor Recently Active?}
    Check1 -->|Yes| Skip[Skip Processing - Return Early]
    Check1 -->|No| Check2{Daily Limit Reached?}
    Check2 -->|Yes| Skip
    Check2 -->|No| Check3{Human Request?}
    Check3 -->|Yes| Skip
    Check3 -->|No| InitState[Initialize Agent State]
    
    InitState --> ParallelStart[Start Parallel Processing]
    
    ParallelStart --> StyleAgent[MentorStyleAgent]
    ParallelStart --> ContextAgent[ContextAnalysisAgent]
    
    StyleAgent --> StyleCache{Cache Hit?}
    StyleCache -->|Yes| StyleCached[Return Cached Style Profile]
    StyleCache -->|No| StyleFetch[Fetch Mentor Messages]
    StyleFetch --> StyleAI{Enough Messages?}
    StyleAI -->|No| StyleQuick[Quick Profile Analysis]
    StyleAI -->|Yes| StyleLLM[LLM Style Analysis via Portkey]
    StyleLLM --> StyleResult[Style Profile Result]
    StyleQuick --> StyleResult
    StyleResult --> StyleCacheStore[Cache Style Profile - 2 hours]
    StyleCached --> StyleComplete[Style Analysis Complete]
    StyleCacheStore --> StyleComplete
    
    ContextAgent --> ContextQuick[Quick Keyword Urgency Check]
    ContextQuick --> UrgencyCheck{Urgency < 0.3?}
    UrgencyCheck -->|Yes| ContextSkip[Skip AI - Use Quick Assessment]
    UrgencyCheck -->|No| ContextFetch[Fetch Conversation History]
    ContextFetch --> ContextLLM[LLM Context Analysis via Portkey]
    ContextLLM --> ContextResult[Context Analysis Result]
    ContextSkip --> ContextResult
    ContextResult --> ContextComplete[Context Analysis Complete]
    
    StyleComplete --> ResponseGen[Response Generation Agent]
    ContextComplete --> ResponseGen
    
    ResponseGen --> ResponseTone{Determine Tone}
    ResponseTone -->|High Urgency| SupportiveTone[Supportive Response]
    ResponseTone -->|Has Question| InformativeTone[Informative Response]
    ResponseTone -->|Default| EncouragingTone[Encouraging Response]
    
    SupportiveTone --> ResponseLLM[LLM Response Generation via Portkey]
    InformativeTone --> ResponseLLM
    EncouragingTone --> ResponseLLM
    
    ResponseLLM --> ResponseQuality[Quality Assessment]
    ResponseQuality --> ResponseComplete[Response Candidate Generated]
    
    ResponseComplete --> ParallelDecision[Parallel: Decision + Suggestions]
    
    ParallelDecision --> DecisionAgent[Decision Agent]
    ParallelDecision --> SuggestionAgent[Intelligent Suggestion Agent]
    
    DecisionAgent --> DecisionFactors[Evaluate Decision Factors]
    DecisionFactors --> Factor1{Mentor Absence > 4hrs?}
    Factor1 -->|No| DecisionNo[Should Not Auto-Respond]
    Factor1 -->|Yes| Factor2{Daily Count < Limit?}
    Factor2 -->|No| DecisionNo
    Factor2 -->|Yes| Factor3{Urgency >= Threshold?}
    Factor3 -->|No| DecisionNo
    Factor3 -->|Yes| Factor4{Style Confidence >= 0.6?}
    Factor4 -->|No| DecisionNo
    Factor4 -->|Yes| DecisionYes[Should Auto-Respond]
    
    SuggestionAgent --> SuggestionUrgency{Urgency < 0.5?}
    SuggestionUrgency -->|Yes| RuleBased[Rule-Based Suggestions]
    SuggestionUrgency -->|No| SuggestionLLM[LLM Suggestions via Portkey]
    SuggestionLLM --> SuggestionResult[Enhanced Suggestions]
    RuleBased --> SuggestionResult
    
    DecisionYes --> SelectResponse[Select Best Response Candidate]
    DecisionNo --> StoreOnly[Store Suggestions Only]
    
    SelectResponse --> Finalize[Finalization Node]
    StoreOnly --> Finalize
    
    Finalize --> TriggerEvents[Trigger Success Events]
    TriggerEvents --> LogInteraction[Log Interaction for Analytics]
    
    SelectResponse --> QueueResponse[Queue AI Response for Delivery]
    QueueResponse --> SendResponse[Send Async AI Response]
    SendResponse --> TagMessage[Tag Message as AI-Generated]
    TagMessage --> NotifyMentor[Notify Mentor of AI Response]
    
    StoreOnly --> NotifySuggestions[Notify Mentor with Suggestions]
    
    NotifyMentor --> End([Processing Complete])
    NotifySuggestions --> End
    Skip --> End
    NormalFlow --> End
    
    style Orchestrator fill:#e1f5fe
    style ParallelStart fill:#fff3e0
    style DecisionYes fill:#c8e6c9
    style DecisionNo fill:#ffccbc
    style Portkey fill:#f3e5f5
```

## Parallel Processing Detail

```mermaid
flowchart LR
    Start[Initial State] --> ThreadPool[ThreadPoolExecutor]
    
    ThreadPool --> Task1[Style Analysis Task]
    ThreadPool --> Task2[Context Analysis Task]
    
    Task1 --> Portkey1[Portkey AI Gateway]
    Task2 --> Portkey2[Portkey AI Gateway]
    
    Portkey1 --> Result1[Style Profile]
    Portkey2 --> Result2[Context Analysis]
    
    Result1 --> Merge[Merge Results]
    Result2 --> Merge
    
    Merge --> ResponseGen[Response Generation]
    ResponseGen --> DecisionPar[Parallel: Decision + Suggestions]
    
    DecisionPar --> DecisionTask[Decision Task]
    DecisionPar --> SuggestionTask[Suggestion Task]
    
    DecisionTask --> Final[Final State]
    SuggestionTask --> Final
    
    style ThreadPool fill:#fff3e0
    style Merge fill:#e1f5fe
    style Final fill:#c8e6c9
```

## Agent Workflow State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialized: Student Message
    
    Initialized --> QuickChecks: Start Processing
    QuickChecks --> Skip: Mentor Active / Limit Reached
    QuickChecks --> ParallelProcessing: Checks Passed
    
    ParallelProcessing --> StyleAnalysis: Start Parallel
    ParallelProcessing --> ContextAnalysis: Start Parallel
    
    StyleAnalysis --> StyleComplete: Analysis Done
    ContextAnalysis --> ContextComplete: Analysis Done
    
    StyleComplete --> ResponseGeneration: Both Complete
    ContextComplete --> ResponseGeneration: Both Complete
    
    ResponseGeneration --> DecisionMaking: Response Generated
    ResponseGeneration --> SuggestionGeneration: Response Generated
    
    DecisionMaking --> AutoResponse: Conditions Met
    DecisionMaking --> SuggestionsOnly: Conditions Not Met
    
    SuggestionGeneration --> Finalization: Suggestions Ready
    
    AutoResponse --> Finalization: Queue Response
    SuggestionsOnly --> Finalization: Store Suggestions
    
    Finalization --> Complete: Events Triggered
    
    Skip --> Complete: Early Exit
    Complete --> [*]
    
    note right of ParallelProcessing
        Style and Context
        run simultaneously
    end note
    
    note right of DecisionMaking
        Decision and Suggestions
        run in parallel
    end note
```

## Cache Flow

```mermaid
flowchart TD
    Request[Style Analysis Request] --> CacheCheck{Cache Exists?}
    CacheCheck -->|Yes| CacheHit[Return Cached Profile - 2hr TTL]
    CacheCheck -->|No| QuickCache{Quick Profile Cache?}
    
    QuickCache -->|Yes| QuickHit[Return Quick Profile - 30min TTL]
    QuickCache -->|No| FetchMessages[Fetch Mentor Messages]
    
    FetchMessages --> MessageCheck{Enough Messages?}
    MessageCheck -->|No| QuickProfile[Generate Quick Profile]
    MessageCheck -->|Yes| RecentCheck{Recent Activity < 5min?}
    
    RecentCheck -->|Yes| QuickProfile
    RecentCheck -->|No| LLMAnalysis[LLM Style Analysis]
    
    LLMAnalysis --> FullProfile[Full Style Profile]
    QuickProfile --> QuickProfileCache[Cache Quick Profile]
    
    FullProfile --> FullProfileCache[Cache Full Profile - 2hr TTL]
    QuickProfileCache --> Return[Return Profile]
    FullProfileCache --> Return
    CacheHit --> Return
    QuickHit --> Return
    
    style CacheHit fill:#c8e6c9
    style QuickHit fill:#fff9c4
    style LLMAnalysis fill:#ffccbc
```

## Decision Flow

```mermaid
flowchart TD
    Start[Decision Agent] --> Check1{Mentor Absence > 4hrs?}
    Check1 -->|No| NoResponse[Mentor Recently Active]
    Check1 -->|Yes| Check2{Daily Count < 3?}
    
    Check2 -->|No| NoResponse[Daily Limit Reached]
    Check2 -->|Yes| Check3{Urgency >= 0.7?}
    
    Check3 -->|No| NoResponse[Low Urgency]
    Check3 -->|Yes| Check4{Style Confidence >= 0.6?}
    
    Check4 -->|No| NoResponse[Insufficient Style Data]
    Check4 -->|Yes| Check5{No Human Request?}
    
    Check5 -->|No| NoResponse[Human Interaction Requested]
    Check5 -->|Yes| AllChecks[All Checks Passed]
    
    AllChecks --> SelectBest[Select Best Response Candidate]
    SelectBest --> AddMetadata[Add Response Metadata]
    AddMetadata --> QueueResponse[Queue Response for Delivery]
    
    NoResponse --> StoreSuggestions[Store Suggestions Only]
    StoreSuggestions --> LogDecision[Log Decision Reason]
    QueueResponse --> LogDecision
    LogDecision --> End([Decision Complete])
    
    style AllChecks fill:#c8e6c9
    style NoResponse fill:#ffccbc
    style QueueResponse fill:#e1f5fe
```

## Error Handling Flow

```mermaid
flowchart TD
    Process[Agent Processing] --> Error{Error Occurred?}
    Error -->|No| Success[Continue Processing]
    Error -->|Yes| ErrorType{Error Type?}
    
    ErrorType -->|LLM API Error| Retry[Retry with Exponential Backoff]
    ErrorType -->|Rate Limit| Queue[Queue for Later Processing]
    ErrorType -->|Network Error| Fallback[Use Fallback Provider]
    ErrorType -->|State Error| Restart[Restart Workflow]
    ErrorType -->|Critical Error| Legacy[Use Legacy System]
    
    Retry --> RetryCheck{Retry Success?}
    RetryCheck -->|Yes| Success
    RetryCheck -->|No| Legacy
    
    Queue --> ProcessLater[Process When Available]
    ProcessLater --> Success
    
    Fallback --> FallbackCheck{Fallback Success?}
    FallbackCheck -->|Yes| Success
    FallbackCheck -->|No| Legacy
    
    Restart --> FreshState[Fresh State Initialization]
    FreshState --> Success
    
    Legacy --> TemplateResponse[Template-Based Response]
    TemplateResponse --> Degraded[Degraded Mode]
    
    Success --> Complete[Processing Complete]
    Degraded --> Complete
    
    style Error fill:#ffccbc
    style Legacy fill:#ff9800
    style Success fill:#c8e6c9
```

## Complete System Architecture

```mermaid
graph TB
    subgraph "Message Layer"
        Student[Student] --> MessageSend[Message Send Core]
        MessageSend --> Queue[Event Queue: ai_mentor_responses]
    end
    
    subgraph "Worker Layer"
        Queue --> Worker[AI Mentor Worker]
        Worker --> EventListener[Event Listener]
    end
    
    subgraph "Orchestrator Layer"
        EventListener --> Orchestrator[AI Agent Orchestrator]
        Orchestrator --> CacheManager[Cache Manager]
    end
    
    subgraph "Agent Layer - Parallel Processing"
        Orchestrator --> StyleAgent[MentorStyleAgent]
        Orchestrator --> ContextAgent[ContextAnalysisAgent]
        Orchestrator --> ResponseAgent[ResponseGenerationAgent]
        Orchestrator --> SuggestionAgent[IntelligentSuggestionAgent]
        Orchestrator --> DecisionAgent[DecisionAgent]
    end
    
    subgraph "AI Gateway Layer"
        StyleAgent --> Portkey[Portkey AI Gateway]
        ContextAgent --> Portkey
        ResponseAgent --> Portkey
        SuggestionAgent --> Portkey
        Portkey --> LLM[LLM Providers<br/>Gemini/OpenAI/etc]
    end
    
    subgraph "State Management"
        Orchestrator --> StateGraph[LangGraph State Machine]
        StateGraph --> Checkpointer[SQLite Checkpointer]
    end
    
    subgraph "Response Layer"
        DecisionAgent --> Decision{Auto-Respond?}
        Decision -->|Yes| ResponseQueue[Queue AI Response]
        Decision -->|No| Suggestions[Store Suggestions]
        ResponseQueue --> AsyncResponse[Async Response Delivery]
        AsyncResponse --> Student
    end
    
    subgraph "Analytics Layer"
        Orchestrator --> Events[Event System]
        Events --> Analytics[Analytics & Logging]
    end
    
    style Orchestrator fill:#e1f5fe
    style Portkey fill:#fff3e0
    style StateGraph fill:#f3e5f5
    style Decision fill:#c8e6c9
```

