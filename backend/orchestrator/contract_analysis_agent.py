"""
Contract Analysis Agent - Dedicated agent for deep contract analysis
Handles large contracts by chunking and focused analysis
"""

import json
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
from langchain_core.tools import tool


class AnalysisState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int
    contract_address: str
    abi: list
    source_code: str
    analysis_results: dict


# Specialized tools for contract analysis
@tool
def analyze_contract_structure(source_code: str) -> str:
    """
    Analyzes the overall structure of a contract.
    Identifies key components: state variables, modifiers, events, main functions.
    
    Args:
        source_code: Full or partial contract source code
        
    Returns:
        JSON string with contract structure overview
    """
    print(f"[STRUCTURE] Analyzing contract structure...")
    
    # Extract key structural elements
    lines = source_code.split('\n')
    
    structure = {
        "state_variables": [],
        "modifiers": [],
        "events": [],
        "functions": [],
        "imports": []
    }
    
    for line in lines:
        line = line.strip()
        
        # State variables (simplified detection)
        if any(line.startswith(t) for t in ['uint', 'address', 'mapping', 'bool', 'string']) and '=' in line:
            structure["state_variables"].append(line[:100])
        
        # Modifiers
        if line.startswith('modifier '):
            structure["modifiers"].append(line.split('(')[0].replace('modifier ', ''))
        
        # Events
        if line.startswith('event '):
            structure["events"].append(line.split('(')[0].replace('event ', ''))
        
        # Functions
        if 'function ' in line:
            func_name = line.split('function ')[1].split('(')[0] if 'function ' in line else None
            if func_name:
                structure["functions"].append(func_name)
        
        # Imports
        if line.startswith('import '):
            structure["imports"].append(line)
    
    return json.dumps(structure, indent=2)


@tool
def analyze_specific_function(source_code: str, function_name: str) -> str:
    """
    Deep analysis of a specific function's logic.
    
    Args:
        source_code: Contract source code
        function_name: Name of function to analyze
        
    Returns:
        Detailed analysis of the function's behavior
    """
    print(f"[FUNCTION] Analyzing function: {function_name}")
    
    # Extract the function code
    lines = source_code.split('\n')
    function_lines = []
    in_function = False
    brace_count = 0
    
    for line in lines:
        if f'function {function_name}' in line:
            in_function = True
        
        if in_function:
            function_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            
            if brace_count == 0 and len(function_lines) > 1:
                break
    
    function_code = '\n'.join(function_lines)
    
    if not function_code:
        return f"Function '{function_name}' not found in source code"
    
    return f"Function code:\n{function_code}\n\n(Ready for LLM analysis)"


@tool
def identify_money_flows(source_code: str) -> str:
    """
    Identifies all money-related operations in the contract.
    
    Args:
        source_code: Contract source code
        
    Returns:
        JSON with all money flows (transfers, receives, balances)
    """
    print(f"[MONEY] Analyzing financial flows...")
    
    money_keywords = [
        'transfer', 'send', 'call{value:', 'payable', 
        'msg.value', 'balance', 'withdraw', 'deposit'
    ]
    
    money_flows = {
        "incoming": [],
        "outgoing": [],
        "balance_checks": []
    }
    
    lines = source_code.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        for keyword in money_keywords:
            if keyword in line_lower:
                context = {
                    "line_number": i + 1,
                    "code": line.strip(),
                    "keyword": keyword
                }
                
                if keyword in ['msg.value', 'payable']:
                    money_flows["incoming"].append(context)
                elif keyword in ['transfer', 'send', 'call{value:']:
                    money_flows["outgoing"].append(context)
                else:
                    money_flows["balance_checks"].append(context)
    
    return json.dumps(money_flows, indent=2)


@tool
def identify_security_risks(source_code: str) -> str:
    """
    Scans for common security vulnerabilities.
    
    Args:
        source_code: Contract source code
        
    Returns:
        JSON with potential security issues
    """
    print(f"[SECURITY] Scanning for vulnerabilities...")
    
    risks = {
        "reentrancy": [],
        "overflow": [],
        "access_control": [],
        "unchecked_calls": []
    }
    
    lines = source_code.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Check for external calls before state changes (reentrancy risk)
        if any(x in line_lower for x in ['.call{', '.transfer(', '.send(']):
            risks["reentrancy"].append({
                "line": i + 1,
                "code": line.strip(),
                "warning": "External call - check if state updated after"
            })
        
        # Check for unchecked arithmetic
        if any(x in line for x in ['+', '-', '*']) and 'SafeMath' not in source_code:
            if 'pragma solidity' in source_code and '0.8' not in source_code:
                risks["overflow"].append({
                    "line": i + 1,
                    "code": line.strip(),
                    "warning": "Arithmetic without SafeMath (pre 0.8)"
                })
        
        # Check for access control
        if 'onlyOwner' in line or 'require(msg.sender' in line:
            risks["access_control"].append({
                "line": i + 1,
                "code": line.strip(),
                "note": "Access control present"
            })
        
        # Unchecked external calls
        if '.call' in line and 'require' not in line and 'if' not in line:
            risks["unchecked_calls"].append({
                "line": i + 1,
                "code": line.strip(),
                "warning": "Unchecked call return value"
            })
    
    return json.dumps(risks, indent=2)


# MUCH MORE FORCEFUL CONTRACT ANALYSIS PROMPT
ANALYSIS_PROMPT = """You are a smart contract security analyst specializing in Solidity.

**CONTRACT INFORMATION:**
Address: {contract_address}
Source Available: {has_source}

**⚠️ MANDATORY REQUIREMENT: YOU MUST USE ALL 4 ANALYSIS TOOLS ⚠️**

You have exactly ONE job: systematically analyze this contract using your tools.

**STEP 1 (REQUIRED):** Call analyze_contract_structure
   - Extract state variables, functions, modifiers, events
   
**STEP 2 (REQUIRED):** Call identify_money_flows  
   - Find all financial operations
   
**STEP 3 (REQUIRED):** Call identify_security_risks
   - Scan for vulnerabilities

**STEP 4 (IF RELEVANT):** Call analyze_specific_function for critical functions
   - Focus on payable functions, withdraw, owner-only functions

**RULES:**
1. You CANNOT skip any of the first 3 tools
2. Do NOT write analysis until AFTER calling all required tools
3. Each tool call gives you data - USE IT in your final report
4. Reference specific line numbers from tool outputs
5. Be thorough but concise

**After using all required tools, structure your response as:**

## 1. CONTRACT OVERVIEW
- Type: [from structure analysis]
- Purpose: [what it does]
- Key components: [from structure]

## 2. FUNCTIONALITY ANALYSIS  
- User capabilities
- Main functions (from structure)
- Function interactions

## 3. MONEY FLOWS 🚨
- Incoming: [from money_flows tool - include line numbers]
- Outgoing: [from money_flows tool - include line numbers]  
- Control: [who manages funds]

## 4. SECURITY ASSESSMENT
- Vulnerabilities: [from security_risks tool - include line numbers]
- Access control: [from security_risks]
- Specific risks with code references

## 5. RISK SUMMARY
🚨 CRITICAL: [immediate fund loss risks]
⚠️ HIGH: [significant risks with conditions]
⚡ MEDIUM: [moderate concerns]
✅ LOW: [minor or mitigated]

## 6. USER GUIDANCE
- Safe usage
- Red flags
- Testing recommendations

**NOW BEGIN: Call analyze_contract_structure IMMEDIATELY.**
"""


def create_analysis_agent():
    """Creates the contract analysis agent with forced tool usage"""
    
    tool_list = [
        analyze_contract_structure,
        analyze_specific_function,
        identify_money_flows,
        identify_security_risks
    ]
    
    model = ChatVertexAI(
        model="gemini-2.0-flash",
        location="global",
        project="avapilot",
        temperature=0.2  # Lower temp for more consistent tool usage
    ).bind_tools(tool_list)
    
    tool_node = ToolNode(tool_list)
    
    def tool_node_with_logging(state):
        print("[CONTRACT ANALYSIS] Executing tools...")
        result = tool_node.invoke(state)
        print("[CONTRACT ANALYSIS] Tools complete")
        return result
    
    def should_continue(state):
        iteration_count = state.get('iteration_count', 0)
        
        # More iterations allowed
        if iteration_count > 15:
            print("[CONTRACT ANALYSIS] ⚠️ Max iterations reached")
            return END
        
        last_message = state['messages'][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tools"
        
        # Check if minimum tools were called
        messages = state['messages']
        tool_call_count = sum(
            1 for msg in messages 
            if hasattr(msg, 'tool_calls') and msg.tool_calls
        )
        
        if tool_call_count < 3:
            print(f"[CONTRACT ANALYSIS] ⚠️ Only {tool_call_count} tools called, need at least 3")
        
        return END
    
    def call_model(state):
        current_count = state.get('iteration_count', 0)
        print(f"[CONTRACT ANALYSIS] Iteration {current_count + 1}")
        
        messages = state['messages']
        
        # On first iteration, add a system message reminder
        if current_count == 0:
            messages = [
                SystemMessage(content="You MUST call analyze_contract_structure as your first action. Do not skip this step.")
            ] + messages
        
        response = model.invoke(messages)
        
        return {
            "messages": [response],
            "iteration_count": current_count + 1
        }
    
    workflow = StateGraph(AnalysisState)
    workflow.add_node("agent", call_model)
    workflow.add_node("call_tools", tool_node_with_logging)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"call_tools": "call_tools", END: END}
    )
    workflow.add_edge('call_tools', 'agent')
    
    return workflow.compile()


def run_contract_analysis(
    contract_address: str,
    abi: list,
    source_code: str = None
) -> str:
    """
    Runs comprehensive contract analysis
    
    Args:
        contract_address: Contract address
        abi: Parsed ABI
        source_code: Source code if available
    
    Returns:
        Comprehensive analysis report
    """
    print("\n" + "="*60)
    print("CONTRACT ANALYSIS AGENT STARTED")
    print("="*60)
    
    has_source = bool(source_code and not source_code.startswith("Error"))
    
    # Chunk large source code
    if has_source and len(source_code) > 12000:
        print(f"[CHUNKING] Source code is large ({len(source_code)} chars), using smart chunking")
        # Keep first 12000 chars which usually contains main logic
        source_code = source_code[:12000] + "\n\n... [Additional code truncated for analysis]"
    
    # Build analysis prompt
    prompt = ANALYSIS_PROMPT.format(
        contract_address=contract_address,
        has_source="Yes (Source Code)" if has_source else "No (ABI Only)"
    )
    
    if has_source:
        prompt += f"\n\n**SOURCE CODE:**\n```solidity\n{source_code}\n```"
    else:
        # Provide function summary from ABI
        functions_summary = "\n".join([
            f"  • {item['name']}({', '.join([inp['type'] for inp in item.get('inputs', [])])}) - {item.get('stateMutability', 'nonpayable')}"
            for item in abi if item.get('type') == 'function'
        ][:30])
        prompt += f"\n\n**ABI FUNCTIONS:**\n{functions_summary}"
    
    graph = create_analysis_agent()
    
    try:
        result = graph.invoke({
            "messages": [HumanMessage(content=prompt)],
            "iteration_count": 0,
            "contract_address": contract_address,
            "abi": abi,
            "source_code": source_code or "",
            "analysis_results": {}
        })
        
        # Extract final analysis from messages
        final_message = result['messages'][-1]
        analysis_text = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        print("="*60)
        print("CONTRACT ANALYSIS COMPLETE")
        print("="*60 + "\n")
        
        return analysis_text
        
    except Exception as e:
        print(f"[ANALYSIS ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error during analysis: {str(e)}"