import type { CustomNode, CustomNodeParameter, NodeDefinition, NodeImplementation, ParamDefinition } from '@/types'

const slugify = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'custom_node'

export const customNodeIdFromDefinitionId = (definitionId: string) => `cn_from_${slugify(definitionId)}`

const pascalize = (value: string) =>
  value.split(/[^a-zA-Z0-9]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('') || 'CustomNode'

const pythonValue = (value: string | number | boolean) => {
  if (typeof value === 'boolean') return value ? 'True' : 'False'
  if (typeof value === 'number') return String(value)
  if (value === 'true' || value === 'false') return value === 'true' ? 'True' : 'False'
  if (value.trim().startsWith('{') || value.trim().startsWith('[')) return value
  return JSON.stringify(value)
}

const customParamType = (param: ParamDefinition): CustomNodeParameter['type'] => {
  if (param.type === 'boolean') return 'bool'
  if (param.type === 'number') return typeof param.defaultValue === 'number' && !Number.isInteger(param.defaultValue) ? 'float' : 'int'
  return 'string'
}

export function createCustomNodeFromDefinition(
  definition: NodeDefinition,
  implementation: NodeImplementation,
): CustomNode {
  const slug = slugify(definition.id)
  const id = customNodeIdFromDefinitionId(definition.id)
  const className = `Custom${pascalize(definition.name)}`
  const now = new Date().toISOString()
  const inputs = definition.inputs.map((port) => port.id).join(', ') || 'inputs'
  const params = definition.params.map((param) => `${param.key}=${pythonValue(param.defaultValue)}`).join(', ')
  const signature = [inputs, params].filter(Boolean).join(', ')

  const starter = [
    `"""Custom implementation derived from ${definition.name}."""`,
    'from rag_studio import CustomNode',
    '',
    `class ${className}(CustomNode):`,
    `    name = ${JSON.stringify(`Custom ${definition.name}`)}`,
    `    category = ${JSON.stringify(definition.category)}`,
    `    basedOn = ${JSON.stringify(`builtin:${definition.id}`)}`,
    '',
    `    def execute(self, ${signature}):`,
    `        # Original implementation: ${implementation.implementation}`,
    '        # Replace this body with your customized logic.',
    '        raise NotImplementedError',
    '',
  ].join('\n')

  const contract = [
    `name: ${JSON.stringify(`Custom ${definition.name}`)}`,
    `basedOn: ${JSON.stringify(`builtin:${definition.id}`)}`,
    `implementation: ${JSON.stringify(implementation.implementation)}`,
    'inputs:',
    ...definition.inputs.map((port) => `  - ${port.id}: ${port.typeLabel}`),
    'outputs:',
    ...definition.outputs.map((port) => `  - ${port.id}: ${port.typeLabel}`),
    'parameters:',
    ...definition.params.map((param) => `  ${param.key}: ${JSON.stringify(param.defaultValue)}`),
    '',
  ].join('\n')

  return {
    id,
    name: `Custom ${definition.name}`,
    slug,
    category: definition.category,
    description: `Derived from the built-in block “${definition.name}”. ${definition.description ?? ''}`.trim(),
    icon: 'sparkles',
    language: 'Python',
    files: [
      { id: 'f_py', name: `${slug}.py`, language: 'python', content: starter, dirty: true },
      { id: 'f_contract', name: 'contract.yaml', language: 'yaml', content: contract, dirty: true },
      { id: 'f_reference', name: `reference_${slug}.py`, language: 'python', content: implementation.source, dirty: false },
    ],
    parameters: definition.params.map((param) => ({
      key: param.key,
      label: param.label,
      type: customParamType(param),
      value: param.defaultValue,
    })),
    inputDefinitions: definition.inputs,
    outputDefinitions: definition.outputs,
    dependencies: [],
    versions: [{
      id: `ver_${slug}`,
      version: 'v1.0.0',
      label: 'Derived draft',
      date: now,
      author: 'You',
      changes: `Created from built-in block ${definition.id}.`,
      current: true,
    }],
    updatedAt: now,
    draftVersion: 'v1.0.0',
    basedOn: `builtin:${definition.id}`,
  }
}
