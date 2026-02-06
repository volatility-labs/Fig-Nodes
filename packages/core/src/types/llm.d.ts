import { z } from 'zod';
export declare const LLMToolFunctionSchema: z.ZodObject<{
    name: z.ZodString;
    description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    name: z.ZodString;
    description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    name: z.ZodString;
    description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMToolSpecSchema: z.ZodObject<{
    type: z.ZodDefault<z.ZodLiteral<"function">>;
    function: z.ZodObject<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    type: z.ZodDefault<z.ZodLiteral<"function">>;
    function: z.ZodObject<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    type: z.ZodDefault<z.ZodLiteral<"function">>;
    function: z.ZodObject<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodString;
        description: z.ZodOptional<z.ZodNullable<z.ZodString>>;
        parameters: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMToolCallFunctionSchema: z.ZodObject<{
    name: z.ZodDefault<z.ZodString>;
    arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    name: z.ZodDefault<z.ZodString>;
    arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    name: z.ZodDefault<z.ZodString>;
    arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMToolCallSchema: z.ZodObject<{
    id: z.ZodDefault<z.ZodString>;
    function: z.ZodDefault<z.ZodObject<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    id: z.ZodDefault<z.ZodString>;
    function: z.ZodDefault<z.ZodObject<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    id: z.ZodDefault<z.ZodString>;
    function: z.ZodDefault<z.ZodObject<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        name: z.ZodDefault<z.ZodString>;
        arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
    }, z.ZodTypeAny, "passthrough">>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMChatMessageSchema: z.ZodObject<{
    role: z.ZodEnum<["system", "user", "assistant", "tool"]>;
    content: z.ZodDefault<z.ZodUnion<[z.ZodString, z.ZodRecord<z.ZodString, z.ZodUnknown>]>>;
    thinking: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    images: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodString, "many">>>;
    tool_calls: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, "many">>>;
    tool_name: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    tool_call_id: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    role: z.ZodEnum<["system", "user", "assistant", "tool"]>;
    content: z.ZodDefault<z.ZodUnion<[z.ZodString, z.ZodRecord<z.ZodString, z.ZodUnknown>]>>;
    thinking: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    images: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodString, "many">>>;
    tool_calls: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, "many">>>;
    tool_name: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    tool_call_id: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    role: z.ZodEnum<["system", "user", "assistant", "tool"]>;
    content: z.ZodDefault<z.ZodUnion<[z.ZodString, z.ZodRecord<z.ZodString, z.ZodUnknown>]>>;
    thinking: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    images: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodString, "many">>>;
    tool_calls: z.ZodOptional<z.ZodNullable<z.ZodArray<z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, "many">>>;
    tool_name: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    tool_call_id: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMChatMetricsSchema: z.ZodObject<{
    total_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    load_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    seed: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    temperature: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    parse_error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    total_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    load_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    seed: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    temperature: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    parse_error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    total_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    load_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    prompt_eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_count: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    eval_duration: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
    seed: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    temperature: z.ZodOptional<z.ZodNullable<z.ZodNumber>>;
    parse_error: z.ZodOptional<z.ZodNullable<z.ZodString>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMToolHistoryItemSchema: z.ZodObject<{
    call: z.ZodUnion<[z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, z.ZodRecord<z.ZodString, z.ZodUnknown>]>;
    result: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    call: z.ZodUnion<[z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, z.ZodRecord<z.ZodString, z.ZodUnknown>]>;
    result: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    call: z.ZodUnion<[z.ZodObject<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
        id: z.ZodDefault<z.ZodString>;
        function: z.ZodDefault<z.ZodObject<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, "passthrough", z.ZodTypeAny, z.objectOutputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">, z.objectInputType<{
            name: z.ZodDefault<z.ZodString>;
            arguments: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
        }, z.ZodTypeAny, "passthrough">>>;
    }, z.ZodTypeAny, "passthrough">>, z.ZodRecord<z.ZodString, z.ZodUnknown>]>;
    result: z.ZodDefault<z.ZodRecord<z.ZodString, z.ZodUnknown>>;
}, z.ZodTypeAny, "passthrough">>;
export declare const LLMThinkingHistoryItemSchema: z.ZodObject<{
    thinking: z.ZodString;
    iteration: z.ZodDefault<z.ZodNumber>;
}, "passthrough", z.ZodTypeAny, z.objectOutputType<{
    thinking: z.ZodString;
    iteration: z.ZodDefault<z.ZodNumber>;
}, z.ZodTypeAny, "passthrough">, z.objectInputType<{
    thinking: z.ZodString;
    iteration: z.ZodDefault<z.ZodNumber>;
}, z.ZodTypeAny, "passthrough">>;
export type LLMToolFunction = z.infer<typeof LLMToolFunctionSchema>;
export type LLMToolSpec = z.infer<typeof LLMToolSpecSchema>;
export type LLMToolCallFunction = z.infer<typeof LLMToolCallFunctionSchema>;
export type LLMToolCall = z.infer<typeof LLMToolCallSchema>;
export type LLMChatMessage = z.infer<typeof LLMChatMessageSchema>;
export type LLMChatMetrics = z.infer<typeof LLMChatMetricsSchema>;
export type LLMToolHistoryItem = z.infer<typeof LLMToolHistoryItemSchema>;
export type LLMThinkingHistoryItem = z.infer<typeof LLMThinkingHistoryItemSchema>;
export type LLMChatMessageList = LLMChatMessage[];
export type LLMToolSpecList = LLMToolSpec[];
export type LLMToolHistory = LLMToolHistoryItem[];
export type LLMThinkingHistory = LLMThinkingHistoryItem[];
export declare function validateLLMToolSpec(obj: unknown): LLMToolSpec | null;
export declare function validateLLMChatMessage(obj: unknown): LLMChatMessage | null;
