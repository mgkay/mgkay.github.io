# Combinatorial Optimization Functions

using Combinatorics
"""
    derangements(n::Int)
Generate derangement of of indices 1 to `n`.

[Source: https://rosettacode.org/wiki/Permutations/Derangements#Julia]
"""
derangements(n::Int) = (perm for perm in permutations(1:n)
                        if all(indx != p for (indx, p) in enumerate(perm)))

"""
    rte2W(rte,f)
Return weight matrix of flow volumes using routings `rte` and their frequencies `f`.
"""
function rte2W(rte,f)
    n = maximum([maximum(i) for i in rte])
    W = zeros(n,n)
    for i in 1:length(f)
        for (j,k) in zip(rte[i][1:end-1],rte[i][2:end])
             W[j,k] += f[i]
        end
    end
    return W
end 


using JuMP, Gurobi
"""
    qapbip(C)
QAP BIP formulation returns permutation matrix `X` given 4-D cost matrix `C`.
"""
function qapbip(C)
    N = 1:size(C,1)
    model = Model(Gurobi.Optimizer)
    @variable(model, X[1:length(N),1:length(N)], Bin )
    @objective(model, Min, sum(C[i,j,k,l]*X[i,k]*X[j,l] for i ∈ N, k ∈ N, j ∈ N, l ∈ N) )
    for k ∈ N
        @constraint(model, sum(X[i,k] for i ∈ N) == 1 )
    end
    for i ∈ N
        @constraint(model, sum(X[i,k] for k ∈ N) == 1 )
    end
    set_optimizer_attribute(model, "OutputFlag", 1)
    set_optimizer_attribute(model, "MIPGap", 0.001)
    set_optimizer_attribute(model, "TimeLimit", 30)
    #set_optimizer_attribute(model, "Heuristics", 0)
    #set_optimizer_attribute(model, "Presolve", 0)
    optimize!(model)
    return value.(X)
end

"""
    sdpi(a,W,D)
Steepest descent pairwise interchange heuristic for QAP.

Returns total cost `TC` and assignment `a` of local optimum given initial assignment `a`, resource-to-resource weight matrix `W`, and site-to-site distance matrix `D`.
"""
function sdpi(aᵒ,W,D)
    cnt = 1
    n = length(aᵒ)
    TCᵒ = sum(W[aᵒ,aᵒ].*D)
    #println(TCᵒ,": ",aᵒ)
    done = false
    while !done
        done = true                 # Assume no improvement will be found
        a₀ = copy(aᵒ)               # Copy as current in case improvement found
        for i = 1:n-1, j = i+1:n
            cnt += 1
            a = copy(a₀)            # Work on copy of current assignment
            a[[j,i]] .= a[[i,j]]    # Pairwise interchange of i and j
            TC = sum(W[a,a].*D)     # Calc. TC of interchange
            if TC < TCᵒ             # Improvement found
                done = false
                TCᵒ, aᵒ = copy(TC), copy(a)
            end
        end
        #println(TCᵒ,": ",aᵒ)
    end
    return (TC = TCᵒ, a = aᵒ, cnt = cnt)   # Named tuple to pass multiple outputs
end

"""
    firstfit(v,V)
First-fit heuristic for bin packing.

Returns array where each element is the indices of items from `v` in a bin. Each element of `v` is the weight of the item and each bin is packed so that its total weight of items does not exceed `V`.
"""
function firstfit(v,V)
    # Put first item into first bin
    B = [[1]]                  # Array of arrays
    b = [v[1]]                 # Array of scalars
    # Add remaining items to bins
    for i = 2:length(v)
        idx = findfirst(b .+ v[i] .<= V)    # Find first bin item fits into
        if ~isnothing(idx)                  # Found existing bin
            b[idx] += v[i]
            push!(B[idx],i)
        else                                # Create new bin for item
            push!(b,v[i])
            push!(B,[i])
        end
    end
    return B
end
    