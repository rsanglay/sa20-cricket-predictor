interface LoadingProps {
  message?: string
}

const Loading = ({ message = 'Loading...' }: LoadingProps) => {
  return (
    <div className="flex min-h-[200px] items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
        <p className="text-sm text-slate-300">{message}</p>
      </div>
    </div>
  )
}

export default Loading
