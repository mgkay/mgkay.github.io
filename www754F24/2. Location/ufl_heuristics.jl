# UFL Heuristics

function ufladd(k, C, y = Int[]; p::Union{Int, Nothing} = nothing)
    if k isa Number
        k = fill(k, size(C, 1))
    end
    fTC(y) = sum(k[y]) + sum(minimum(C[y, :], dims=1))
    TCᵒ = isempty(y) ? Inf : fTC(y)
    N = 1:size(C, 1) 
    done = false
    while !done
        TC, i = Inf, nothing
        for i′ = setdiff(N, y)
            TC′ = fTC(vcat(y, i′))
            if TC′ < TC
                TC, i = TC′, i′
            end
        end
        if (p === nothing && TC < TCᵒ) || (p isa Int && length(y) < p)
            TCᵒ, y = TC, push!(y, i)
        else
            done = true
        end
    end
    return y, TCᵒ
end

function ufldrop(k, C, y = nothing; p::Union{Int, Nothing} = nothing)
    if k isa Number
        k = fill(k, size(C, 1))
    end
    fTC(y) = sum(k[y]) + sum(minimum(C[y, :], dims=1))
    if y === nothing
        y = 1:size(C, 1)
    end
    TCᵒ = fTC(y)
    done = false
    while !done && length(y) > 1
        TC, i = Inf, nothing
        for i′ in y
            TC′ = fTC(setdiff(y, i′))
            if TC′ < TC
                TC, i = TC′, i′
            end
        end
        if (p === nothing && TC < TCᵒ) || (p isa Int && length(y) > p)
            TCᵒ, y = TC, setdiff(y, i)
        else
            done = true
        end
    end
    return y, TCᵒ
end

function swap!(y::Vector{Int}, i::Int, j::Int)
    deleteat!(y, findfirst(==(i), y))  # Remove i from y
    push!(y, j)  # Add j to y
end

# Revert function: Reverse the swap, remove j from y, and add i back
function revert!(y::Vector{Int}, i::Int, j::Int)
    deleteat!(y, findfirst(==(j), y))  # Remove j from y
    push!(y, i)  # Add i back to y
end

function uflxchg(k, C, y::Vector{Int})
    if k isa Number
        k = fill(k, size(C, 1))
    end
    fTC(y) = sum(k[y]) + sum(minimum(C[y, :], dims=1))
    N = 1:size(C, 1)
    TCᵒ = fTC(y)
    done = false
    while length(y) > 1 && !done     # No exchange if 1 NF
        TC, i, j = Inf, nothing, nothing
        for i′ in  y
            for j′ in setdiff(N, y)
                swap!(y, i′, j′)     # Swap i' in y with j'
                TC′ = fTC(y)  
                if TC′ < TC
                    TC, i, j = TC′, i′, j′
                end
                revert!(y, i′, j′)   # Restore original y
            end
        end
        if TC < TCᵒ
            TCᵒ = TC
            swap!(y, i, j)
        else
            done = true
        end
    end
    return y, TCᵒ
end

function ufl(k, C, dodisp = true)
    y′, TC′ = ufladd(k, C)
    dodisp ? println("  Add: ", TC′) : nothing
    y, TC = y′, TC′
    done = false
    while !done
        y, TC = uflxchg(k, C, y′)
        dodisp ? println(" Xchg: ", TC) : nothing
        if Set(y) !== Set(y′)
            y′, TC′ = ufladd(k, C, y)
            dodisp ? println("  Add: ", TC′) : nothing
            y′′, TC′′ = ufldrop(k, C, y)
            dodisp ? println(" Drop: ", TC′′) : nothing
            if TC′′ < TC′
                y′, TC′ = y′′, TC′′
            end
            if TC′ >= TC
                done = true
            end
        else
            done = true
        end
    end
    return y, TC
end

function pmedian(p, C)
    y = ufladd(0, C, p = p)[1]
    return uflxchg(0, C, y)
end

