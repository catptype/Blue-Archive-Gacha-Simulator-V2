document.addEventListener('DOMContentLoaded', () => {
    const mainGrid = document.getElementById('main-grid');
    const leftColumn = document.getElementById('left-column');

    let activeGroupId = document.querySelector('.character-group:not(.opacity-0)')?.id;
    
    // A variable to hold the ID of our animation loop
    let animationFrameId = null;

    // ==========================================================================
    // SECTION 1: SIDEBAR EXPANSION & CAROUSEL SYNCHRONIZATION
    // ==========================================================================
    
    /**
     * Instantly updates the carousel's center position. This is called on every
     * frame during the sidebar animation to ensure perfect synchronization.
     */
    function recenterActiveCarouselInstantly() {
        if (activeGroupId) {
            const activeGroupElement = document.getElementById(activeGroupId);
            if (activeGroupElement) {
                updateCarousel(activeGroupElement, true); // instant re-center
            }
        }
    }

    /**
     * Starts a high-performance animation loop that runs for 300ms, matching the
     * CSS transition duration of the sidebar.
     */
    function startAnimationLoop() {
        // Cancel any previous loop to prevent conflicts
        if (animationFrameId) cancelAnimationFrame(animationFrameId);

        const animationDuration = 300; // Must match the CSS transition duration
        let startTime = null;

        const loop = (currentTime) => {
            if (!startTime) startTime = currentTime;
            const elapsedTime = currentTime - startTime;

            recenterActiveCarouselInstantly();

            if (elapsedTime < animationDuration) {
                // If the animation is not finished, request the next frame
                animationFrameId = requestAnimationFrame(loop);
            } else {
                 // Final check to ensure it lands perfectly
                 recenterActiveCarouselInstantly();
            }
        };

        // Start the loop
        animationFrameId = requestAnimationFrame(loop);
    }

    leftColumn.addEventListener('mouseenter', () => {
        mainGrid.classList.add('sidebar-expanded');
        startAnimationLoop();
    });

    leftColumn.addEventListener('mouseleave', () => {
        mainGrid.classList.remove('sidebar-expanded');
        startAnimationLoop();
    });

    // --- 2. ADVANCED SEAMLESS CAROUSEL LOGIC ---
    const carouselState = {};
    const CLONE_COUNT = 3; // Number of items to clone on each side for the seamless effect

    function updateCarousel(group, instant = false) {
        const slider = group.querySelector('.slider-container');
        const state = carouselState[group.id];

        slider.style.transitionDuration = instant ? '0ms' : '600ms';
        slider.style.transitionTimingFunction = instant ? '' : 'ease-in-out';
        
        const containerWidth = group.offsetWidth;
        const cardWidth = state.cards[0].offsetWidth;
        const margin = parseInt(window.getComputedStyle(state.cards[0]).marginRight) * 2;
        const cardAndMarginWidth = cardWidth + margin;
        
        const offsetToCenter = (containerWidth / 2) - (cardAndMarginWidth / 2);
        const newX = offsetToCenter - (state.currentIndex * cardAndMarginWidth);
        
        slider.style.transform = `translateX(${newX}px)`;

        state.cards.forEach((card, i) => {
            const nameElement = card.querySelector('.character-name');
            // We use the 'realIndex' to correctly identify the active card, ignoring clones
            const realIndex = (state.currentIndex - CLONE_COUNT + state.totalRealCards) % state.totalRealCards;
            const cardRealIndex = parseInt(card.dataset.realIndex);

            if (realIndex === cardRealIndex) {
                card.style.transform = 'scale(1.15)'; 
                card.style.opacity = '1';
                card.classList.remove('grayscale');
                nameElement.classList.remove('opacity-0', '-translate-x-8');
                nameElement.classList.add('opacity-100', 'translate-x-0');
            } else {
                card.style.transform = 'scale(0.9)';
                card.style.opacity = '0.5';
                card.classList.add('grayscale');
                nameElement.classList.remove('opacity-100', 'translate-x-0');
                nameElement.classList.add('opacity-0', '-translate-x-8');
            }
        });
    }

    // --- Setup logic for each carousel ---
    document.querySelectorAll('.character-group').forEach(group => {
        const slider = group.querySelector('.slider-container');
        const originalCards = Array.from(group.querySelectorAll('.character-card'));
        const totalRealCards = originalCards.length;
        if (totalRealCards === 0) return;

        // Assign a real index to each original card for later identification
        originalCards.forEach((card, i) => card.dataset.realIndex = i);

        // Cloning for seamless effect
        const clonesStart = originalCards.slice(-CLONE_COUNT).map(c => c.cloneNode(true));
        const clonesEnd = originalCards.slice(0, CLONE_COUNT).map(c => c.cloneNode(true));
        
        slider.append(...clonesEnd);
        slider.prepend(...clonesStart);

        const allCards = Array.from(slider.querySelectorAll('.character-card'));

        carouselState[group.id] = {
            currentIndex: CLONE_COUNT, // Start at the first "real" item
            totalRealCards: totalRealCards,
            cards: allCards,
            isTransitioning: false
        };

        setTimeout(() => updateCarousel(group, true), 100);

        // --- Event Listeners for seamless looping ---
        group.querySelector('.nav-left')?.addEventListener('click', () => {
            const state = carouselState[group.id];
            if (state.isTransitioning) return;
            state.currentIndex--;
            updateCarousel(group);
            state.isTransitioning = true;
        });

        group.querySelector('.nav-right')?.addEventListener('click', () => {
            const state = carouselState[group.id];
            if (state.isTransitioning) return;
            state.currentIndex++;
            updateCarousel(group);
            state.isTransitioning = true;
        });

        // The magic happens here: check for clones after transition ends
        slider.addEventListener('transitionend', () => {
            const state = carouselState[group.id];
            state.isTransitioning = false;
            
            // If we are on a clone at the end, jump to the first real item
            if (state.currentIndex >= state.totalRealCards + CLONE_COUNT) {
                state.currentIndex = CLONE_COUNT;
                updateCarousel(group, true);
            }
            // If we are on a clone at the start, jump to the last real item
            if (state.currentIndex < CLONE_COUNT) {
                state.currentIndex = state.totalRealCards + CLONE_COUNT - 1;
                updateCarousel(group, true);
            }
        });
    });

    // --- 3. SCHOOL SELECTION ---
    const schoolSelectors = document.querySelectorAll('.school-button');

    schoolSelectors.forEach(button => {
        button.addEventListener('click', () => {
            const schoolId = button.dataset.schoolId;
            const newGroupId = `school-group-${schoolId}`;
            if (newGroupId === activeGroupId) return;

            schoolSelectors.forEach(btn => btn.classList.remove('active', 'ring-2', 'ring-sky-400'));
            button.classList.add('active', 'ring-2', 'ring-sky-400');
            
            const oldGroup = document.getElementById(activeGroupId);
            if (oldGroup) oldGroup.classList.add('opacity-0', 'pointer-events-none');

            const newGroup = document.getElementById(newGroupId);
            if (newGroup) {
                newGroup.classList.remove('opacity-0', 'pointer-events-none');
                updateCarousel(newGroup, true);
                
                // This is the only update needed. The string ID is our "source of truth".
                activeGroupId = newGroupId; 
            }
        });
    });
    
    window.addEventListener('resize', () => {
        if (activeGroupId) updateCarousel(document.getElementById(activeGroupId), true);
    });
});