document.addEventListener('DOMContentLoaded', () => {
    // --- =============================================================== ---
    // --- SECTION 1: INITIALIZATION & DOM REFERENCES                      ---
    // --- =============================================================== ---
    const mainGrid = document.getElementById('main-grid');
    const leftColumn = document.getElementById('left-column');
    const carouselStage = document.getElementById('carousel-stage');
    const loadingSpinner = document.getElementById('loading-spinner');
    
    let activeGroupId = null;
    let animationFrameId = null;
    const schoolDataCache = {};
    let isLoading = false;
    const carouselState = {};
    const CLONE_COUNT = 3;

    // --- =============================================================== ---
    // --- SECTION 2: CORE CAROUSEL & ANIMATION LOGIC                      ---
    // --- =============================================================== ---
    
    /**
     * The main function that controls the carousel's appearance and position.
     * This is the same trusted logic from your original code.
     */
    function updateCarousel(group, instant = false) {
        if (!group) return; // Safety check
        const slider = group.querySelector('.slider-container');
        const state = carouselState[group.id];
        if (!state || !state.cards.length) return; // More safety checks

        slider.style.transitionDuration = instant ? '0ms' : '600ms';
        slider.style.transitionTimingFunction = instant ? '' : 'ease-in-out';
        
        const containerWidth = group.offsetWidth;
        const cardWidth = state.cards[0].offsetWidth;
        const margin = parseInt(window.getComputedStyle(state.cards[0]).marginRight) * 2;
        const cardAndMarginWidth = cardWidth + margin;
        const offsetToCenter = (containerWidth / 2) - (cardAndMarginWidth / 2);
        const newX = offsetToCenter - (state.currentIndex * cardAndMarginWidth);
        
        slider.style.transform = `translateX(${newX}px)`;

        state.cards.forEach((card) => {
            const nameElement = card.querySelector('.character-name');
            const realIndex = (state.currentIndex - CLONE_COUNT + state.totalRealCards) % state.totalRealCards;
            const cardRealIndex = parseInt(card.dataset.realIndex);

            if (realIndex === cardRealIndex) { // Active card
                card.style.transform = 'scale(1.15)'; 
                card.style.opacity = '1';
                card.classList.remove('grayscale');
                nameElement.classList.remove('opacity-0', '-translate-x-8');
                nameElement.classList.add('opacity-100', 'translate-x-0');
            } else { // Inactive card
                card.style.transform = 'scale(0.9)';
                card.style.opacity = '0.5';
                card.classList.add('grayscale');
                nameElement.classList.remove('opacity-100', 'translate-x-0');
                nameElement.classList.add('opacity-0', '-translate-x-8');
            }
        });
    }

    /**
     * This function contains the setup logic for a NEWLY created carousel.
     * It handles cloning, state initialization, and attaching event listeners.
     */
    function initializeCarousel(group) {
        const slider = group.querySelector('.slider-container');
        const originalCards = Array.from(group.querySelectorAll('.character-card'));
        const totalRealCards = originalCards.length;
        if (totalRealCards === 0) return;

        originalCards.forEach((card, i) => card.dataset.realIndex = i);

        const clonesStart = originalCards.slice(-CLONE_COUNT).map(c => c.cloneNode(true));
        const clonesEnd = originalCards.slice(0, CLONE_COUNT).map(c => c.cloneNode(true));
        slider.append(...clonesEnd);
        slider.prepend(...clonesStart);

        carouselState[group.id] = {
            currentIndex: CLONE_COUNT,
            totalRealCards: totalRealCards,
            cards: Array.from(slider.querySelectorAll('.character-card')),
            isTransitioning: false
        };

        setTimeout(() => updateCarousel(group, true), 100);

        // --- Event Listeners for Arrow Navigation ---
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

        slider.addEventListener('transitionend', () => {
            const state = carouselState[group.id];
            if (!state) return;
            state.isTransitioning = false;
            
            if (state.currentIndex >= state.totalRealCards + CLONE_COUNT) {
                state.currentIndex = CLONE_COUNT;
                updateCarousel(group, true);
            }
            if (state.currentIndex < CLONE_COUNT) {
                state.currentIndex = state.totalRealCards + CLONE_COUNT - 1;
                updateCarousel(group, true);
            }
        });
    }

    // --- =============================================================== ---
    // --- SECTION 3: DYNAMIC DATA LOADING & RENDERING                     ---
    // --- =============================================================== ---

    /**
     * Creates the HTML string for a new carousel from student data.
     */
    function buildCarouselHTML(schoolId, students) {
        if (!students || students.length === 0) {
            return `
                <div class="character-group w-full h-full flex items-center justify-center">
                    <p class="text-xl text-slate-400">No students found for this school.</p>
                </div>
            `;
        }

        const studentCardsHTML = students.map(student => `
            <div class="character-card flex-shrink-0 w-[300px] h-[85%] mx-4 transition-all duration-500 ease-in-out" data-real-index="${student.id}">
                 <div class="relative w-full h-full group">
                    <img src="/image/student/${student.id}/portrait" alt="${student.name}" class="w-full h-full object-cover rounded-lg">
                     <div class="character-name absolute bottom-[20px] left-[70px] opacity-0 transition-all duration-500 ease-in-out transform -translate-x-8">
                         <h2 class="text-5xl font-black text-white uppercase tracking-widest origin-bottom-left transform -rotate-90" style="text-shadow: 2px 2px 10px rgba(0, 0, 0, 0.7);">${student.name}</h2>
                     </div>
                 </div>
            </div>
        `).join('');

        // --- MODIFICATION ---
        // The new carousel is now created with 'opacity-0' so it's invisible by default.
        // A 'transition-opacity' class is added to allow it to fade in smoothly.
        return `
            <div id="school-group-${schoolId}" class="character-group absolute inset-0 opacity-0 transition-opacity duration-500 ease-in-out">
                <div class="slider-container absolute top-0 left-0 w-full h-full flex items-center">${studentCardsHTML}</div>
                <button class="nav-arrow nav-left absolute left-6 top-1/2 -translate-y-1/2 bg-black/40 p-3 rounded-full hover:bg-sky-500/50 transition-colors z-40">
                    <svg class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
                </button>
                <button class="nav-arrow nav-right absolute right-6 top-1/2 -translate-y-1/2 bg-black/40 p-3 rounded-full hover:bg-sky-500/50 transition-colors z-40">
                    <svg class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
                </button>
            </div>
        `;
    }

    /**
     * Fetches student data, then builds and initializes the carousel with a smooth fade-in.
     */
    async function loadSchoolData(schoolId) {
        if (isLoading) return;
        isLoading = true;

        // Step 1: Fade out the CURRENT carousel (if one exists).
        const currentGroup = activeGroupId ? document.getElementById(activeGroupId) : null;
        if (currentGroup) {
            currentGroup.classList.add('opacity-0');
        }
        
        // Step 2: Show the loading spinner.
        loadingSpinner.style.display = 'flex';
        
        // A short delay to allow the fade-out animation to be visible.
        // Optional but good for UX: wait for fade-out to be visible before fetching.
        await new Promise(resolve => setTimeout(resolve, 300));

        // Step 3: Fetch data (from cache or server).
        let students = [];
        if (schoolDataCache[schoolId]) {
            students = schoolDataCache[schoolId];
        } else {
            try {
                const response = await fetch(`/api/school/${schoolId}/students/`);
                if (!response.ok) throw new Error('Network response failed');
                const data = await response.json();
                students = data.students;
                schoolDataCache[schoolId] = students;
            } catch (error) {
                console.error("Failed to fetch student data:", error);
            }
        }
        
        // Step 4: Build and inject the new, INVISIBLE carousel into the stage.
        const carouselHTML = buildCarouselHTML(schoolId, students);
        carouselStage.innerHTML = carouselHTML;
        
        // Step 5: Get a reference to the new group and initialize its logic while it's still invisible.
        const newGroup = document.getElementById(`school-group-${schoolId}`);
        if (newGroup && students && students.length > 0) {
            // This initializes the carousel (sets up clones, state, etc.) while it is still invisible.
            initializeCarousel(newGroup);
        }
        
        activeGroupId = `school-group-${schoolId}`;
        loadingSpinner.style.display = 'none'; // Hide spinner.
        
        // --- THE FIX ---
        // Step 6: Use a tiny timeout. This forces the browser to process the initial 'opacity-0'
        // state BEFORE it tries to apply the final 'opacity-100' state, which guarantees
        // the CSS transition will fire correctly.
        setTimeout(() => {
            if (newGroup) {
                newGroup.classList.remove('opacity-0');
            }
        }, 50); // A small delay like 20ms is enough.
        
        isLoading = false;
    }
    
    // --- =============================================================== ---
    // --- SECTION 4: EVENT LISTENERS                                      ---
    // --- =============================================================== ---

    // --- Sidebar animation synchronization ---
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

        // The 'loop' function is called by the browser on every frame.
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

    // Event listeners to trigger the synchronized animation.
    leftColumn.addEventListener('mouseenter', () => {
        mainGrid.classList.add('sidebar-expanded');
        startAnimationLoop();
    });

    leftColumn.addEventListener('mouseleave', () => {
        mainGrid.classList.remove('sidebar-expanded');
        startAnimationLoop();
    });

    // --- School selection ---
    const schoolSelectors = document.querySelectorAll('.school-button');
    schoolSelectors.forEach(button => {
        button.addEventListener('click', () => {
            const schoolId = button.dataset.schoolId;
            const newGroupId = `school-group-${schoolId}`;
            if (newGroupId === activeGroupId || isLoading) return;

            schoolSelectors.forEach(btn => btn.classList.remove('active', 'ring-2', 'ring-sky-400'));
            button.classList.add('active', 'ring-2', 'ring-sky-400');
            
            loadSchoolData(schoolId);
        });
    });
    
    // --- Window resizing ---
    window.addEventListener('resize', () => {
        if (activeGroupId) updateCarousel(document.getElementById(activeGroupId), true);
    });

    // --- Kickstart the page by loading the first school's data ---
    const firstSchoolButton = document.querySelector('.school-button');
    if (firstSchoolButton) {
        loadSchoolData(firstSchoolButton.dataset.schoolId);
    } else {
        loadingSpinner.style.display = 'none';
        carouselStage.innerHTML = '<p class="text-xl text-slate-400 text-center mt-20">No schools available.</p>';
    }
});