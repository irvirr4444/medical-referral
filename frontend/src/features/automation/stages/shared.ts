import type {
  AutomationMicrostep,
  ImplementationStatus,
  MicrostepExample,
  MicrostepRunStatus,
} from '../types'

interface StepOptions {
  id: string
  name: string
  description: string
  system: string
  next: string
  input: string
  output: string
  validation: string
  duration?: string
  implementationStatus?: ImplementationStatus
  runStatus?: MicrostepRunStatus
  exception?: {
    input: string
    output: string
    validation: string
    status?: MicrostepRunStatus
  }
}

function example(
  status: MicrostepRunStatus,
  duration: string,
  input: string,
  output: string,
  validation: string,
): MicrostepExample {
  return {
    status,
    duration,
    inputs: [{ label: 'Received', value: input }],
    outputs: [{ label: 'Produced', value: output }],
    validation,
  }
}

export function step(options: StepOptions): AutomationMicrostep {
  const implementationStatus = options.implementationStatus ?? 'working'
  const runStatus =
    options.runStatus ??
    (implementationStatus === 'planned'
      ? 'planned'
      : implementationStatus === 'partial'
        ? 'attention'
        : 'completed')

  return {
    id: options.id,
    name: options.name,
    description: options.description,
    implementationStatus,
    system: options.system,
    next: options.next,
    example: example(
      runStatus,
      options.duration ?? 'Under 1 second',
      options.input,
      options.output,
      options.validation,
    ),
    exceptionExample: options.exception
      ? example(
          options.exception.status ?? 'attention',
          options.duration ?? 'Under 1 second',
          options.exception.input,
          options.exception.output,
          options.exception.validation,
        )
      : undefined,
  }
}
